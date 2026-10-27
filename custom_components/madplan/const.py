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
Her er de seneste uger fra familiens madplan i Google Docs:
{madplan_text}

I dag er det: {weekday}.
Dagens dato er: {date}.

Opgave:
Find ud af hvad der skal spises til aftensmad i dag.
Regler:
1. Find den uge i madplanen der matcher den aktuelle uge eller dato. Den nyeste uge står altid øverst.
2. Hvis ugen har specifikke ugedage (f.eks. "Mandag", "Tirsdag", etc.), vælg den ret der matcher i dag.
3. Hvis ugen er en nummereret liste eller punktopstillet række med 7 retter uden ugedage, svarer 1. ret til Mandag, 2. ret til Tirsdag, 3. ret til Onsdag, 4. ret til Torsdag, 5. ret til Fredag, 6. ret til Lørdag og 7. ret til Søndag.
4. Rens retten for links (URLs), emojis, kommentarer som "(ungerne laver selv)", "(Jacob laver mad)" eller lange ingredienslister, så det blot er det rene, appetitlige navn på retten (f.eks. "Paprikasuppe med flutes", "Indbagt laks" eller "Kylling i karry").
5. Hvis der intet står for i dag, returner "Ikke planlagt".
"""
