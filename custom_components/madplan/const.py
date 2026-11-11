"""Constants for the Madplan integration."""

DOMAIN = "madplan"
NAME = "Madplan"

CONF_GOOGLE_DOC_URL = "google_doc_url"
CONF_AI_ENTITY = "ai_entity"
CONF_AI_PROMPT = "ai_prompt"
CONF_UPDATE_TIME = "update_time"
CONF_SYNC_ENTITY = "sync_entity"

DEFAULT_GOOGLE_DOC_URL = "https://docs.google.com/document/d/1wzkKe4pnGYY364drWIu9UozcK_6apwUjFxBoWwy6KOQ/edit"
DEFAULT_AI_ENTITY = "ai_task.google_ai_task"
DEFAULT_UPDATE_TIME = "06:30"
DEFAULT_SYNC_ENTITY = "input_text.ai_genereret_aftensmad"

DEFAULT_AI_PROMPT = """Du er en præcis assistent for en dansk familie.
Her er familiens madplan fra Google Docs (de nyeste og fremtidige uger står øverst):
{madplan_text}

I dag er det: {weekday} d. {date}.
Aktuel uge: Uge {week_number}.

Opgave:
Find ud af hvad der skal spises til aftensmad i dag.

Vigtige regler:
1. Tag udgangspunkt i den AKTUELLE ugebetegnelse: Uge {week_number} (eller matchende datoer {date}).
   BEMÆRK: Familien planlægger fremad og har ofte skrevet 1 eller 2 fremtidige uger øverst i dokumentet (f.eks. Uge {next_week} eller Uge {next_next_week}). Du må ALDRIG bare tage den øverste uge i dokumentet! Du skal specifikt finde sektionen for "Uge {week_number}" (eller "Madplan uge {week_number}").
2. Hvis ugen har specifikke ugedage (f.eks. "{weekday} : ..."), vælg retten der matcher i dag ({weekday}).
3. Hvis ugen er en nummereret eller punktopstillet liste med 7 retter uden ugedage, svarer 1. ret til Mandag, 2. ret til Tirsdag, 3. ret til Onsdag, 4. ret til Torsdag, 5. ret til Fredag, 6. ret til Lørdag og 7. ret til Søndag.
4. Rens retten for links (URLs), emojis, kommentarer som "(ungerne laver selv)", "(Jacob laver mad)", "(rester)" eller lange ingredienslister/kildeangivelser, så det udelukkende er det rene, appetitlige navn på retten (f.eks. "Kold pastasalat", "Paprikasuppe med flutes", "Indbagt laks" eller "Kylling i karry").
5. Hvis der absolut intet står for {weekday} i Uge {week_number}, returner "Ikke planlagt".
"""
