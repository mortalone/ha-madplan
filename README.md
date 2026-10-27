# Madplan — Home Assistant Custom Integration

En Home Assistant integration til automatisk at hente familiens madplan fra Google Docs og lade AI (Google Generative AI / Gemini) udtrække dagens ret til dashboards og billedgeneratorer.

## Funktioner

- **Fuld UI Konfiguration (Config Flow & Options Flow)**:
  - Indtast/skift Google Docs URL direkte i Home Assistant under *Indstillinger → Enheder & Tjenester*.
  - Justér AI-instruktionerne (prompten) direkte fra UI.
  - Vælg hvilken AI-model (`ai_task` eller `conversation`) der skal bruges.
  - Vælg dagligt opdateringstidspunkt (standard `06:30`).
  - Synkroniser automatisk til en hjælper (f.eks. `input_text.ai_genereret_aftensmad`).
- **Entiteter**:
  - `sensor.madplan_dagens_ret`: Viser dagens ret.
  - `button.madplan_opdater`: Knap til on-demand opdatering.
- **Service**:
  - `madplan.update`: Service der kan kaldes fra scripts eller automations.

## Installation

### Manuel installation
Kopier mappen `custom_components/madplan` til din Home Assistant `config/custom_components/madplan`.
Genstart Home Assistant.
Gå derefter til **Indstillinger → Enheder & Tjenester → Tilføj integration** og søg efter **Madplan**.

### HACS
Tilføj dette repository som et brugerdefineret repository i HACS som en **Integration**.
