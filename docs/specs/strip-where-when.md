# Where and when at a glance

Status: **done**.

Part of the [wing-alert spec](wing-alert.md): slice 17. Requirement IDs (`FR-17.x`) are unique across all spec files.

## Slice 17: Where and when at a glance

Branch `feat/strip-where-when`.

The day strip says how windy a day gets, but not where or when: you have to open Sunday to find out it's Buckroney from 11. On a phone the table hides the wind arrows, so the direction isn't shown anywhere. And Magheramore goes: nobody rides it.

```text
Wide screen                                      Phone
 ‹  Sat 28        Sun 29        Mon 30      ›     Sat 28   Sun 29   Mon 30
    ↗ 22 kn       ↗ 19 kn       ↗ 32 kn           ↗22 kn   ↗19 kn   ↗32 kn
    Arklow        Buckroney     Ennereilly        Arklow   Buckro…  Ennere…
    09:00–15:00   11:00–15:00   09:00–15:00       09–15    11–15    09–15
    ⚠️ shore break ⚠️ shore break 🚨 shore break     ⚠️        ⚠️        🚨
```

- **FR-17.1** **Where and when in the day strip.** Each day with a window describes its best window (top-ranked, FR-1.5): its top wind with an arrow for the direction (pointing where the wind blows to, as in the table), the spot, and its hours. The number is now that window's top wind, not the peak of all the day's windows (FR-9.4), so the tile tells one story: the peak could come from another spot. The calendar (FR-16.2) shows the same number, so the two agree. On a phone the spot name is cut with "…" when it doesn't fit, the hours are `11–15`, and the shore break warning is just ⚠️ or 🚨 (as in the calendar). The tile's title gives it all in full, e.g. `Buckroney 11:00–15:00 · 19 kn WSW · Shore break: watch out · 1.1 m waves at 5 s`. A day with no window still shows "–".
- **FR-17.2** **Wind arrows on a phone.** The table's cells keep their arrow on a phone, on its own small line at the top of the cell above the wind, as there's no room beside it in a 22 px cell. Each cell then reads top to bottom: direction, wind, gust, waves, like Windguru's rows but per spot. Same for the measured rows (FR-11.1). Rows get a little taller. Wide screens don't change.
- **FR-17.3** **No Magheramore.** It leaves `config/spots.yaml` and the spot table, so it's no longer forecast, mapped or alerted. Past days' pages still show it: they come from the runs as issued (FR-9.3).
