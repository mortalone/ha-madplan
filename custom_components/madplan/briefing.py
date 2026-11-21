"""Live weekly briefing builder for Madplan and REMA 1000."""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_CACHED_BRIEFING: dict[str, Any] | None = None
_CACHE_TIMESTAMP: datetime.datetime | None = None
_CACHE_TTL = datetime.timedelta(minutes=5)
_FETCH_LOCK: asyncio.Lock | None = None


def invalidate_briefing_cache() -> None:
    """Invalidate cache when items are modified."""
    global _CACHE_TIMESTAMP
    _CACHE_TIMESTAMP = None

CALENDARS = [
    "calendar.webcal_app_quinyx_com_webcal_id_0522d9330dd20f48274897f77cad1c13",
    "calendar.webcal_app_quinyx_com_webcal_id_110e6dcba970bdf665a37998cd88b8cf",
    "calendar.fam_nyrup_hansen_dk",
    "calendar.dictes_kalender_events",
    "calendar.maltes_kalender_events",
    "calendar.siljes_kalender_events",
    "calendar.helligdage_i_danmark",
    "calendar.danmark",
]

FASTE_MAERKEDAGE = {
    "01-01": "Nytårsdag (Nem mad / burgere / pizza)",
    "02-14": "Valentinsdag",
    "06-05": "Grundlovsdag & Fars dag",
    "06-23": "Sankt Hans Aften (Grill / bålmad)",
    "10-31": "Halloween (Græskar / uhyggelig familiemad)",
    "11-10": "Mortensaften (Traditionelt and / andebryst med rødkål og brunede kartofler)",
    "12-23": "Lillejuleaften (Oplagt med risengrød)",
    "12-24": "Juleaften (And / flæskesteg / festmåltid)",
    "12-25": "1. Juledag",
    "12-26": "2. Juledag (Julefrokost)",
    "12-31": "Nytårsaften (Festmenu)",
}

WEEKDAYS_DA = [
    "Mandag",
    "Tirsdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lørdag",
    "Søndag",
]


async def async_get_ugens_briefing(
    hass: HomeAssistant, force: bool = False
) -> dict[str, Any]:
    """Fetch calendar events, todo items, rules and offers with intelligent caching."""
    global _CACHED_BRIEFING, _CACHE_TIMESTAMP, _FETCH_LOCK
    now = datetime.datetime.now()

    if not force and _CACHED_BRIEFING is not None and _CACHE_TIMESTAMP is not None:
        if now - _CACHE_TIMESTAMP < _CACHE_TTL:
            res = dict(_CACHED_BRIEFING)
            res["cached"] = True
            res["sidst_opdateret"] = _CACHE_TIMESTAMP.strftime("%H:%M:%S")
            return res

    if _FETCH_LOCK is None:
        _FETCH_LOCK = asyncio.Lock()

    async with _FETCH_LOCK:
        if not force and _CACHED_BRIEFING is not None and _CACHE_TIMESTAMP is not None:
            if datetime.datetime.now() - _CACHE_TIMESTAMP < _CACHE_TTL:
                return _CACHED_BRIEFING

        _LOGGER.info("Opdaterer Madplan ugebriefing fra kalendere og REMA...")
        briefing = await _build_ugens_briefing(hass)
        _CACHED_BRIEFING = briefing
        _CACHE_TIMESTAMP = datetime.datetime.now()
        briefing["sidst_opdateret"] = _CACHE_TIMESTAMP.strftime("%H:%M:%S")
        return briefing


async def _build_ugens_briefing(hass: HomeAssistant) -> dict[str, Any]:
    """Fetch calendar events, todo items, rules and offers, then build briefing."""
    now = datetime.datetime.now()
    cur_m = now.month

    if cur_m in [12, 1, 2]:
        cur_season = "Vinter"
        cur_season_guide = (
            "Varm og mættende mad: simremad, fyldige supper, rodfrugter, gryderetter. "
            "I december: oplagt med risengrød og traditionel julehyggemad."
        )
    elif cur_m in [3, 4, 5]:
        cur_season = "Forår"
        cur_season_guide = (
            "Friske forårsgrøntsager, asparges, kylling, fisk og lettere retter."
        )
    elif cur_m in [6, 7, 8]:
        cur_season = "Sommer"
        cur_season_guide = (
            "Lette, friske retter der ikke er for tunge i varmen: grill, salater, koldskål, hurtig pasta."
        )
    else:
        cur_season = "Efterår"
        cur_season_guide = (
            "Efterårsvarme og råvarer i sæson: rodfrugter, kål, svampe, simreretter og supper. "
            "Husk faste efterårstraditioner som Mortensaften (and)."
        )

    # 1. Fetch calendar events for next 8 days
    cal_events_dict: dict[str, Any] = {}
    try:
        cal_res = await hass.services.async_call(
            "calendar",
            "get_events",
            {"duration": {"days": 8}},
            target={"entity_id": CALENDARS},
            blocking=True,
            return_response=True,
        )
        if isinstance(cal_res, dict):
            cal_events_dict = cal_res.get("service_response") or cal_res
    except Exception as err:
        _LOGGER.warning("Kunne ikke hente kalenderbegivenheder til briefing: %s", err)

    # 2. Fetch REMA 1000 todo list items
    todo_items: list[dict[str, Any]] = []
    try:
        todo_res = await hass.services.async_call(
            "todo",
            "get_items",
            {"status": ["needs_action"]},
            target={"entity_id": "todo.middagsro_indkobsliste"},
            blocking=True,
            return_response=True,
        )
        if isinstance(todo_res, dict):
            s_res = todo_res.get("service_response") or todo_res
            todo_items = (
                s_res.get("todo.middagsro_indkobsliste", {}).get("items", [])
            )
    except Exception as err:
        _LOGGER.warning("Kunne ikke hente to-do varer til briefing: %s", err)

    # 3. Read custom rules from todo.familiens_madregler
    todo_rules: list[str] = []
    try:
        rules_res = await hass.services.async_call(
            "todo",
            "get_items",
            {"status": ["needs_action"]},
            target={"entity_id": "todo.familiens_madregler"},
            blocking=True,
            return_response=True,
        )
        if isinstance(rules_res, dict):
            s_res = rules_res.get("service_response") or rules_res
            items = (
                s_res.get("todo.familiens_madregler", {}).get("items", [])
                if isinstance(s_res, dict)
                else []
            )
            todo_rules = [i.get("summary") for i in items if i.get("summary")]
    except Exception as err:
        _LOGGER.warning("Kunne ikke hente regler fra todo.familiens_madregler: %s", err)

    def _get_helper(entity_id: str, default: str) -> str:
        state = hass.states.get(entity_id)
        if state and state.state not in ["unknown", "unavailable", ""]:
            return state.state
        return default

    regler = {
        "brugerens_aktive_regler": todo_rules,
        "jacob_kok": _get_helper(
            "input_text.regel_jacob_kok", "Enkle hverdagsretter, max 30-40 minutter"
        ),
        "lotte_kok": _get_helper(
            "input_text.regel_lotte_kok", "Frie kulinariske tøjler"
        ),
        "ungerne_alene": _get_helper(
            "input_text.regel_ungerne_alene",
            "Nem mad (f.eks. færdige pizzabunde) eller forskudt restemad",
        ),
        "weekend_fredag": _get_helper(
            "input_text.regel_weekendmad",
            "Fredag hyggemad (pizza/burger/tacos), lør/søn god steg eller simremad",
        ),
        "weekend_loerdag_soendag": _get_helper(
            "input_text.regel_weekendmad",
            "Fredag hyggemad (pizza/burger/tacos), lør/søn god steg eller simremad",
        ),
        "tilbud_inspiration": "Kig efter ugens tilbud og lad dem inspirere ugens kød og råvarer, men lad ikke planen være 100% dikteret af tilbud.",
        "butiksprioritering_tilbud": "Lokale butikker prioriteres ALTID først (REMA 1000 altid nr. 1, derefter Netto og SuperBrugsen). Herefter baseret på afstand: Meny (Maribo), Føtex, Kvickly og til sidst SPAR. Hvis lokale butikker har varen på tilbud, skal tilbud fra fjernere butikker IKKE foreslås.",
        "inspiration_google_doc": "Hent gerne inspiration i alle de retter, der er skrevet i Google Docs dokumentet gennem årene (familiens gennemprøvede livretter).",
        "nye_spaendende_retter": "Foreslå også meget gerne nye, spændende retter udefra, som er varierede og passer til familiens smag, sæson og køkkenniveau.",
        "ingen_gentagelser_paa_ugen": "Ingen to ens retter på en uge, MEDMINDRE der planlægges store portioner, som kan spises dagen efter eller forskudt med en dag imellem (f.eks. til dage hvor ungerne er alene hjemme).",
        "rotation_uger": 4,
    }

    favoritter = {
        "aeg": "Skrabeæg 10 stk (str. M/L)",
        "floedekartofler": "Hjemmelavede med rigtige kartofler og piskefløde 36%",
        "maelk": "Arla Økologisk Skummetmælk 0,1%",
        "paalaeg": "Pålækker (rullepølse, hamburgerryg)",
        "ris": "Langk. Øko Jasminris",
        "rugbroed": "Mørkt solsikkerugbrød eller Schulstad Barbaras",
        "smoer": "Lurpak Saltet Smør",
        "tomater": "REMA 1000 Økologiske Hakkede Tomater (gerne 3 dåser til kødsovs)",
    }

    genkoeb_radar = {
        "husholdning_3_5_uger": _get_helper(
            "input_text.radar_husholdning_3_5_uger",
            "Opvasketabs, bagepapir, fryseposer (3L/4L), stanniol, køkkenrulle, toiletpapir",
        ),
        "pleje_3_5_uger": _get_helper(
            "input_text.radar_pleje_3_5_uger",
            "Tandstikker m/tandtråd, tandpasta, trusseindlæg/bind, håndsæbe, shampoo",
        ),
        "drikkevarer": _get_helper(
            "input_text.radar_drikkevarer",
            "1664 Blanc, Pepsi Max",
        ),
        "ugentlig_basis": "Skummetmælk, rugbrød, smør, pålæg, æg, frugt/gnavegrønt",
    }

    # 4. Read best offers from sensors (split into active now and upcoming)
    def _store_rank(store_name: str) -> int:
        s = (store_name or "").lower().strip()
        if "rema" in s:
            return 1
        if "netto" in s:
            return 2
        if "superbrugsen" in s or "super brugsen" in s or "brugsen" in s:
            return 3
        if "meny" in s:
            return 4
        if "føtex" in s or "fotex" in s:
            return 5
        if "kvickly" in s:
            return 6
        if "spar" in s:
            return 7
        return 99

    def _pick_best_by_store_priority(offers_list: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not offers_list:
            return None
        # Tier 1: Local (REMA 1000, Netto, SuperBrugsen)
        # Tier 2: Meny Maribo
        # Tier 3: Føtex, Kvickly, SPAR and others
        tier1 = [o for o in offers_list if _store_rank(o.get("store", "")) <= 3]
        tier2 = [o for o in offers_list if _store_rank(o.get("store", "")) == 4]
        tier3 = [o for o in offers_list if _store_rank(o.get("store", "")) > 4]

        candidates = tier1 if tier1 else (tier2 if tier2 else tier3)
        return min(candidates, key=lambda x: (_store_rank(x.get("store", "")), x.get("price", 9999)))

    def _get_best_offer(sensor_id: str) -> dict[str, Any] | None:
        state = hass.states.get(sensor_id)
        if not state:
            return None
        offers = state.attributes.get("offers") or []
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        active_list = []
        upcoming_list = []
        for o in offers:
            rf = o.get("run_from")
            rt = o.get("run_till")
            try:
                f_dt = datetime.datetime.fromisoformat(rf.replace("Z", "+00:00")) if rf else None
                t_dt = datetime.datetime.fromisoformat(rt.replace("Z", "+00:00")) if rt else None
            except Exception:
                f_dt, t_dt = None, None
            if f_dt and t_dt:
                if f_dt <= now_dt <= t_dt:
                    active_list.append(o)
                elif f_dt > now_dt:
                    upcoming_list.append(o)

        best_act = _pick_best_by_store_priority(active_list)
        best_up = _pick_best_by_store_priority(upcoming_list)

        result: dict[str, Any] = {}
        if best_act:
            result["aktivt_nu"] = {
                "butik": best_act.get("store"),
                "navn": best_act.get("heading"),
                "pris": best_act.get("price"),
                "enhed": best_act.get("description"),
                "udlober": best_act.get("run_till", "")[:10] if best_act.get("run_till") else "",
            }
        if best_up:
            result["kommende"] = {
                "butik": best_up.get("store"),
                "navn": best_up.get("heading"),
                "pris": best_up.get("price"),
                "enhed": best_up.get("description"),
                "gaelder_fra": best_up.get("run_from", "")[:10] if best_up.get("run_from") else "",
                "udlober": best_up.get("run_till", "")[:10] if best_up.get("run_till") else "",
            }
        if not result and state.attributes.get("best_offer"):
            result["best_offer"] = state.attributes.get("best_offer")
        return result

    ugens_bedste_tilbud = {
        "lurpak": _get_best_offer("sensor.tilbud_lurpak"),
        "hakket_oksekod": _get_best_offer("sensor.tilbud_hakket_oksekod"),
        "kyllingebryst": _get_best_offer("sensor.tilbud_kyllingebryst"),
        "pepsi_max": _get_best_offer("sensor.tilbud_pepsi_max"),
        "blanc_1664": _get_best_offer("sensor.tilbud_1664_blanc"),
    }

    # 5. Extract events for individual calendars
    lotte_cal = "calendar.webcal_app_quinyx_com_webcal_id_0522d9330dd20f48274897f77cad1c13"
    jacob_cal = "calendar.webcal_app_quinyx_com_webcal_id_110e6dcba970bdf665a37998cd88b8cf"
    fam_cal = "calendar.fam_nyrup_hansen_dk"
    dicte_cal = "calendar.dictes_kalender_events"
    malte_cal = "calendar.maltes_kalender_events"
    silje_cal = "calendar.siljes_kalender_events"
    hol_cal = "calendar.helligdage_i_danmark"
    dnk_cal = "calendar.danmark"

    l_events = cal_events_dict.get(lotte_cal, {}).get("events", [])
    j_events = cal_events_dict.get(jacob_cal, {}).get("events", [])
    f_events = cal_events_dict.get(fam_cal, {}).get("events", [])
    d_events = cal_events_dict.get(dicte_cal, {}).get("events", [])
    m_events = cal_events_dict.get(malte_cal, {}).get("events", [])
    s_events = cal_events_dict.get(silje_cal, {}).get("events", [])
    h_events = cal_events_dict.get(hol_cal, {}).get("events", []) + cal_events_dict.get(dnk_cal, {}).get("events", [])

    # 6. Build day-by-day overview for next 7 days
    days: list[dict[str, Any]] = []
    for i in range(1, 8):
        target_dt = now + datetime.timedelta(days=i)
        target_date = target_dt.strftime("%Y-%m-%d")
        target_md = target_dt.strftime("%m-%d")
        day_name = WEEKDAYS_DA[target_dt.weekday()]

        # Lotte shift
        ns_l_work = False
        ns_l_desc = "Fri / hjemme"
        for ev in l_events:
            ev_start = str(ev.get("start", ""))[:10]
            ev_end = str(ev.get("end", ""))[:10]
            if ev_start <= target_date <= ev_end:
                summary = str(ev.get("summary", "")).lower()
                desc = str(ev.get("description", "")).lower()
                if "fridøgn" in summary or "fridøgn" in desc:
                    ns_l_desc = "Planlagt fridøgn"
                else:
                    ns_l_work = True
                    start_t = str(ev.get("start", ""))[11:16]
                    end_t = str(ev.get("end", ""))[11:16]
                    loc = ev.get("location", "Toreby")
                    ns_l_desc = f"Arbejde {start_t}-{end_t} ({loc})"

        # Jacob shift
        ns_j_work = False
        ns_j_desc = "Fri / hjemme"
        for ev in j_events:
            ev_start = str(ev.get("start", ""))[:10]
            ev_end = str(ev.get("end", ""))[:10]
            if ev_start <= target_date <= ev_end:
                summary = str(ev.get("summary", "")).lower()
                desc = str(ev.get("description", "")).lower()
                if "fridøgn" in summary or "fridøgn" in desc:
                    ns_j_desc = "Planlagt fridøgn"
                else:
                    ns_j_work = True
                    start_t = str(ev.get("start", ""))[11:16]
                    end_t = str(ev.get("end", ""))[11:16]
                    loc = ev.get("location", "Sølyst")
                    ns_j_desc = f"Arbejde {start_t}-{end_t} ({loc})"

        # Kids
        kids_events: list[str] = []
        for ev in f_events + d_events + m_events + s_events:
            ev_start = str(ev.get("start", ""))[:10]
            if ev_start == target_date:
                summary = ev.get("summary")
                if summary and summary not in kids_events:
                    kids_events.append(summary)

        # Holidays & special occasions
        hol_name = FASTE_MAERKEDAGE.get(target_md)
        if not hol_name:
            for ev in h_events:
                ev_start = str(ev.get("start", ""))[:10]
                if ev_start == target_date:
                    hol_name = ev.get("summary")
                    break
        if target_dt.month == 12 and not hol_name and target_dt.weekday() in [4, 5, 6]:
            hol_name = "December julehygge (oplagt til risengrød)"

        # Cook logic
        if ns_l_work and ns_j_work:
            cook = "Ungerne alene / Færdigret"
            guideline = regler["ungerne_alene"]
        elif ns_l_work and not ns_j_work:
            cook = "Jacob"
            guideline = regler["jacob_kok"]
        elif not ns_l_work and ns_j_work:
            cook = "Lotte"
            guideline = regler["lotte_kok"]
        else:
            cook = "Lotte eller Jacob (begge hjemme)"
            if target_dt.weekday() == 4:
                guideline = regler["weekend_fredag"]
            elif target_dt.weekday() in [5, 6]:
                guideline = regler["weekend_loerdag_soendag"]
            else:
                guideline = "Begge er hjemme. Frie tøjler eller hyggelig familiemad."

        if hol_name:
            guideline += f" [MÆRKEDAG]: {hol_name}"

        days.append({
            "dato": target_date,
            "ugedag": day_name,
            "lotte": ns_l_desc,
            "jacob": ns_j_desc,
            "boern_og_faelles": kids_events if kids_events else "Ingen særlige planer",
            "maerkedag": hol_name,
            "kok": cook,
            "anbefaling": guideline,
        })

    mangler = [i.get("summary") for i in todo_items if i.get("summary")]

    # 7. Fetch Google Docs meal plan & 4-week history from madplan sensor
    doc_state = hass.states.get("sensor.madplan_dagens_ret")
    google_doc_data: dict[str, Any] = {}
    history_preview = ""
    if doc_state:
        attrs = doc_state.attributes
        history_preview = attrs.get("preview", "")
        persistent_history = attrs.get("persistent_history", {})
        google_doc_data = {
            "dagens_ret": doc_state.state,
            "dagens_kok": attrs.get("dagens_kok"),
            "dagens_note": attrs.get("dagens_note"),
            "aktuel_uge_nummer": attrs.get("uge"),
            "ugens_madplan": attrs.get("ugens_madplan", []),
            "naeste_uge_nummer": attrs.get("naeste_uge_nummer"),
            "naeste_uges_madplan": attrs.get("naeste_uges_madplan", []),
            "google_doc_url": attrs.get("google_doc_url"),
            "google_doc_raat_indhold": history_preview,
            "persistent_madhistorik": persistent_history,
        }

    return {
        "status": "success",
        "standard_personer": 5,
        "saeson": cur_season,
        "saeson_retningslinjer": cur_season_guide,
        "regler": regler,
        "familie_favoritter": favoritter,
        "genkoeb_radar": genkoeb_radar,
        "aktuel_rema_indkobsliste": {
            "mangler_at_kobe": mangler,
            "antal_mangler": len(mangler),
        },
        "ugens_bedste_tilbud": ugens_bedste_tilbud,
        "butiks_strategi": {
            "primaer": "REMA 1000",
            "lokale_alternativer": ["Netto", "MENY (Meny Rønnede)", "Lidl"],
            "princip": (
                "Saml det primære indkøb i REMA. Hvis der er markante besparelser eller specialvarer "
                "i lokale butikker (f.eks. smørtilbud eller pizzabunde i Netto, fersk fisk/suppe i Meny), "
                "fremhæv det i chatten og tilføj varen til REMA-listen som en uspecificeret note med butiksnavn."
            ),
        },
        "google_docs_madplan": google_doc_data,
        "historik_seneste_fire_uger": history_preview,
        "madplan_historik_og_dokument": history_preview,
        "uge_oversigt": days,
    }
