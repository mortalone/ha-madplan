"""DataUpdateCoordinator for the Madplan integration."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any


import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_AI_ENTITY,
    CONF_AI_PROMPT,
    CONF_GOOGLE_DOC_URL,
    CONF_SYNC_ENTITY,
    CONF_UPDATE_TIME,
    DEFAULT_AI_ENTITY,
    DEFAULT_AI_PROMPT,
    DEFAULT_GOOGLE_DOC_URL,
    DEFAULT_SYNC_ENTITY,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DANISH_WEEKDAYS = [
    "Mandag",
    "Tirsdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lørdag",
    "Søndag",
]


def normalize_google_doc_url(url: str) -> str:
    """Ensure the Google Doc URL exports as plain text."""
    if not url:
        return ""
    clean_url = url.strip()
    if "/export?format=txt" in clean_url:
        return clean_url
    if "/edit" in clean_url:
        return clean_url.split("/edit")[0] + "/export?format=txt"
    if clean_url.endswith("/"):
        clean_url = clean_url[:-1]
    return f"{clean_url}/export?format=txt"


def parse_week_section(content: str) -> list[dict[str, Any]]:
    """Parse 7 days of meals and cook from a week section."""
    days = DANISH_WEEKDAYS
    result = []
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    # 1. Match day names (Mandag : Ret)
    day_matches = {}
    for line in lines:
        for idx, day_name in enumerate(days):
            m = re.match(rf"^{day_name}\b[:\s-]*(.*)", line, re.IGNORECASE)
            if m:
                day_matches[idx] = m.group(1).strip()
                break

    if len(day_matches) >= 3:
        for idx, day_name in enumerate(days):
            raw = day_matches.get(idx, "Ikke planlagt")
            result.append({"dag": day_name, "raw": raw})
    else:
        # 2. Match numbered list 1-7
        num_matches = {}
        for line in lines:
            m = re.match(r"^([1-7])[\.\:\s-]+(.*)", line)
            if m:
                num = int(m.group(1))
                num_matches[num - 1] = m.group(2).strip()
        for idx, day_name in enumerate(days):
            raw = num_matches.get(idx, "Ikke planlagt")
            result.append({"dag": day_name, "raw": raw})

    # Clean dish name and parse cook
    clean_result = []
    for item in result:
        raw = item["raw"]
        if raw == "Ikke planlagt" or not raw:
            clean_result.append({
                "dag": item["dag"],
                "ret": "Ikke planlagt",
                "kok": "—",
                "note": "",
                "er_planlagt": False,
            })
            continue

        # Extract notes in parentheses
        notes = re.findall(r"\((.*?)\)", raw)
        note_str = ", ".join(notes)

        # Determine cook
        cook = "Far / Mor"
        raw_lower = raw.lower()
        if any(w in raw_lower for w in ["jacob", "far"]):
            cook = "Far"
        elif any(w in raw_lower for w in ["dicte", "malte", "silje", "ungerne", "børnene"]):
            cook = "Børnene"
        elif "lotte" in raw_lower or "mor" in raw_lower:
            cook = "Mor"

        # Clean dish name
        clean_ret = re.sub(r"\(.*?\)", "", raw)
        clean_ret = re.sub(r"https?://\S+", "", clean_ret)
        clean_ret = re.sub(r"[🍲🐟🌮🥬🌭🍳🍤🥪🍝🧀🍗🥗🥙]", "", clean_ret)
        clean_ret = clean_ret.strip(" -:–,")

        clean_result.append({
            "dag": item["dag"],
            "ret": clean_ret if clean_ret else raw,
            "kok": cook,
            "note": note_str,
            "er_planlagt": True,
        })
    return clean_result


def get_week_plan(doc_text: str, target_week: int) -> list[dict[str, Any]] | None:
    """Find and parse a specific week number from the Google Doc text.
    
    The Google Doc is in reverse chronological order (newest at the top).
    Only inspect entries in the current year's cycle (before week numbers jump back up to previous year's 50-52).
    """
    weeks = re.split(r"(?i)(?:^|\n)\s*(?:madplan\s*)?uge\s*(\d+)", doc_text)
    entries = []
    for i in range(1, len(weeks), 2):
        try:
            entries.append((int(weeks[i]), weeks[i + 1]))
        except (ValueError, IndexError):
            continue

    current_year_entries = []
    prev_w = None
    for w, content in entries:
        if prev_w is not None and w > prev_w + 3:
            # Jumped to previous year's week numbers (e.g. week 1 -> week 52)
            break
        current_year_entries.append((w, content))
        prev_w = w

    for w, content in current_year_entries:
        if w == target_week:
            return parse_week_section(content)
    return None


class MadplanCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    """Coordinator to fetch Google Doc meal plan and query AI."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.entry_data = entry_data
        self._unsub_time: Any = None
        self._setup_schedule()

    @property
    def google_doc_url(self) -> str:
        """Get Google Doc URL from entry options or data."""
        return self.entry_data.get(CONF_GOOGLE_DOC_URL, DEFAULT_GOOGLE_DOC_URL)

    @property
    def ai_entity(self) -> str:
        """Get AI entity."""
        return self.entry_data.get(CONF_AI_ENTITY, DEFAULT_AI_ENTITY)

    @property
    def ai_prompt(self) -> str:
        """Get AI prompt."""
        return self.entry_data.get(CONF_AI_PROMPT, DEFAULT_AI_PROMPT)

    @property
    def update_time(self) -> str:
        """Get update time in HH:MM format."""
        return self.entry_data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)

    @property
    def sync_entity(self) -> str:
        """Get entity to synchronize with."""
        return self.entry_data.get(CONF_SYNC_ENTITY, DEFAULT_SYNC_ENTITY)

    def update_config(self, new_data: dict[str, Any]) -> None:
        """Update coordinator configuration and reschedule."""
        self.entry_data = new_data
        self._setup_schedule()

    def _setup_schedule(self) -> None:
        """Register daily scheduled trigger."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_str = self.update_time or DEFAULT_UPDATE_TIME
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            hour = 6
            minute = 30

        async def _scheduled_update(*_: Any) -> None:
            _LOGGER.info("Scheduled daily madplan update running at %02d:%02d", hour, minute)
            await self.async_request_refresh()

        self._unsub_time = async_track_time_change(
            self.hass,
            _scheduled_update,
            hour=hour,
            minute=minute,
            second=0,
        )
        _LOGGER.debug("Scheduled madplan daily update at %02d:%02d:00", hour, minute)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch meal plan from Google Docs and parse with AI."""
        export_url = normalize_google_doc_url(self.google_doc_url)
        if not export_url:
            raise UpdateFailed("Ingen Google Docs URL konfigureret")

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(export_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Fejl ved download af Google Doc (HTTP {resp.status})"
                    )
                doc_text = (await resp.text(encoding="utf-8")).lstrip("\ufeff")
        except Exception as err:
            raise UpdateFailed(f"Kunne ikke forbinde til Google Docs: {err}") from err

        if not doc_text or not doc_text.strip():
            raise UpdateFailed("Det hentede Google Doc er tomt")

        # De seneste uger findes øverst i dokumentet. Sættes til 15000 tegn så fremadrettede uger
        # med opskrifter/noter ikke afskærer den aktuelle uges retter.
        text_preview = doc_text[:15000]

        now = dt_util.now()
        weekday_name = DANISH_WEEKDAYS[now.weekday()]
        date_str = now.strftime("%d/%m")
        iso_year, week_number, iso_weekday = now.isocalendar()
        next_week = (now + timedelta(days=7)).isocalendar().week
        next_next_week = (now + timedelta(days=14)).isocalendar().week
        prev_week = (now - timedelta(days=7)).isocalendar().week

        # Parse ugens madplan og næste uges madplan direkte fra de seneste uger
        ugens_madplan = get_week_plan(text_preview, week_number)
        naeste_uges_madplan = get_week_plan(text_preview, next_week)

        # Berig ugens madplan med Quinyx vagter og familiens kalender
        cal_events = {}
        try:
            monday_dt = now - timedelta(days=now.weekday())
            sunday_dt = monday_dt + timedelta(days=7)
            cal_res = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "start_date_time": monday_dt.strftime("%Y-%m-%dT00:00:00"),
                    "end_date_time": sunday_dt.strftime("%Y-%m-%dT23:59:59"),
                },
                target={
                    "entity_id": [
                        "calendar.webcal_app_quinyx_com_webcal_id_0522d9330dd20f48274897f77cad1c13",
                        "calendar.webcal_app_quinyx_com_webcal_id_110e6dcba970bdf665a37998cd88b8cf",
                        "calendar.fam_nyrup_hansen_dk",
                    ]
                },
                blocking=True,
                return_response=True,
            )
            if isinstance(cal_res, dict):
                cal_events = cal_res.get("service_response") or cal_res
        except Exception as err:
            _LOGGER.debug("Kunne ikke hente kalenderbegivenheder til madplan: %s", err)

        lotte_events = cal_events.get("calendar.webcal_app_quinyx_com_webcal_id_0522d9330dd20f48274897f77cad1c13", {}).get("events", [])
        jacob_events = cal_events.get("calendar.webcal_app_quinyx_com_webcal_id_110e6dcba970bdf665a37998cd88b8cf", {}).get("events", [])
        fam_events = cal_events.get("calendar.fam_nyrup_hansen_dk", {}).get("events", [])

        monday_dt = now - timedelta(days=now.weekday())
        for idx, item in enumerate(ugens_madplan or []):
            item["er_i_dag"] = (idx == now.weekday())
            day_dt = monday_dt + timedelta(days=idx)
            day_str = day_dt.strftime("%Y-%m-%d")

            # Tjek Lottes vagt
            lotte_work = False
            lotte_time = ""
            for ev in lotte_events:
                s = str(ev.get("start", ""))[:10]
                e = str(ev.get("end", ""))[:10]
                if s <= day_str <= e:
                    summ = str(ev.get("summary", "")).lower()
                    desc = str(ev.get("description", "")).lower()
                    if "fridøgn" not in summ and "fridøgn" not in desc:
                        lotte_work = True
                        st = str(ev.get("start", ""))[11:16]
                        et = str(ev.get("end", ""))[11:16]
                        lotte_time = f"{st}–{et}" if st and et else "arbejder"

            # Tjek Jacobs vagt
            jacob_work = False
            jacob_time = ""
            for ev in jacob_events:
                s = str(ev.get("start", ""))[:10]
                e = str(ev.get("end", ""))[:10]
                if s <= day_str <= e:
                    summ = str(ev.get("summary", "")).lower()
                    desc = str(ev.get("description", "")).lower()
                    if "fridøgn" not in summ and "fridøgn" not in desc:
                        jacob_work = True
                        st = str(ev.get("start", ""))[11:16]
                        et = str(ev.get("end", ""))[11:16]
                        jacob_time = f"{st}–{et}" if st and et else "arbejder"

            # Tjek familiens arrangementer (f.eks. julefrokost, fest, spiser ude)
            fam_note = ""
            jacob_away = False
            for ev in fam_events:
                s = str(ev.get("start", ""))[:10]
                if s == day_str:
                    summ = str(ev.get("summary", ""))
                    summ_l = summ.lower()
                    if any(w in summ_l for w in ["julefrokost", "fest", "spiser ude", "fødselsdag"]):
                        st = str(ev.get("start", ""))[11:16]
                        fam_note = f"{summ} ({st})" if st else summ
                        if "far" in summ_l or "jacob" in summ_l:
                            jacob_away = True

            # Hvis der ikke er sat en eksplicit manuel kok i Google Doc'et (default 'Far / Mor')
            manual_note = item.get("note", "")
            if item.get("kok") in ["Far / Mor", "—", ""]:
                if jacob_away:
                    item["kok"] = "Mor"
                    item["note"] = manual_note or fam_note or "Far spiser ude"
                elif lotte_work and not jacob_work:
                    item["kok"] = "Far"
                    item["note"] = manual_note or f"Mor arbejder ({lotte_time})"
                elif not lotte_work and jacob_work:
                    item["kok"] = "Mor"
                    item["note"] = manual_note or f"Far arbejder ({jacob_time})"
                elif lotte_work and jacob_work:
                    item["kok"] = "Ungerne alene"
                    item["note"] = manual_note or "Begge arbejder"
                elif fam_note:
                    item["note"] = manual_note or fam_note

        # Flag 'er_i_dag' på ugens madplan samt find dagens ret & kok
        dagens_ret = "Ikke fundet"
        dagens_kok = "Far / Mor"
        dagens_note = ""

        if ugens_madplan and len(ugens_madplan) > now.weekday():
            today_item = ugens_madplan[now.weekday()]
            if today_item.get("er_planlagt"):
                dagens_ret = today_item.get("ret", "Ikke fundet")
                dagens_kok = today_item.get("kok", "Far / Mor")
                dagens_note = today_item.get("note", "")

        # Hvis regex ikke fandt dagens ret (eller den er uplanlagt), fallback til AI Task
        if not dagens_ret or dagens_ret in ["Ikke fundet", "Ikke planlagt"]:
            prompt = self.ai_prompt
            prompt = prompt.replace("{madplan_text}", text_preview)
            prompt = prompt.replace("{weekday}", weekday_name)
            prompt = prompt.replace("{date}", date_str)
            prompt = prompt.replace("{week_number}", str(week_number))
            prompt = prompt.replace("{next_week}", str(next_week))
            prompt = prompt.replace("{next_next_week}", str(next_next_week))
            prompt = prompt.replace("{prev_week}", str(prev_week))
            prompt = prompt.replace("{year}", str(now.year))

            try:
                ai_res = await self.hass.services.async_call(
                    "ai_task",
                    "generate_data",
                    {
                        "entity_id": self.ai_entity,
                        "task_name": "Find dagens aftensmad",
                        "instructions": prompt,
                        "structure": {
                            "dagens_ret": {
                                "description": "Det rene navn på dagens ret",
                                "required": True,
                                "selector": {"text": {"multiline": False}},
                            }
                        },
                    },
                    blocking=True,
                    return_response=True,
                )

                if isinstance(ai_res, dict):
                    data = ai_res.get("data")
                    if isinstance(data, dict):
                        dagens_ret = data.get("dagens_ret", "Ikke fundet")
                    elif isinstance(data, str):
                        dagens_ret = data
            except Exception as err:
                _LOGGER.warning("Fejl ved kald til %s: %s", self.ai_entity, err)
                if not dagens_ret:
                    dagens_ret = "Fejl ved AI analyse"

        # Rens svar hvis nødvendigt
        if dagens_ret:
            dagens_ret = dagens_ret.strip().strip('"').strip("'")

        # Synkroniser til input_text hjælper hvis konfigureret
        sync_target = self.sync_entity
        if sync_target and self.hass.states.get(sync_target) is not None:
            try:
                await self.hass.services.async_call(
                    "input_text",
                    "set_value",
                    {"entity_id": sync_target, "value": dagens_ret[:255]},
                    blocking=True,
                )
                _LOGGER.debug("Synkroniserede dagens ret '%s' til %s", dagens_ret, sync_target)
            except Exception as sync_err:
                _LOGGER.warning("Kunne ikke opdatere %s: %s", sync_target, sync_err)

        return {
            "dagens_ret": dagens_ret,
            "dagens_kok": dagens_kok,
            "dagens_note": dagens_note,
            "ugens_madplan": ugens_madplan or [],
            "naeste_uges_madplan": naeste_uges_madplan,
            "naeste_uge_nummer": next_week,
            "uge": week_number,
            "ugedag": weekday_name,
            "dato": date_str,
            "sidst_opdateret": now.isoformat(),
            "google_doc_url": self.google_doc_url,
            "raw_text_preview": text_preview[:2000],
        }


    def async_unload(self) -> None:
        """Clean up registered timer."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None
