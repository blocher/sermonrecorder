# ADR 0007: Confirmed nearby Church suggestions

## Status

Accepted

## Decision

- Recording never requests or depends on location.
- A signed-in Congregant may explicitly request nearby Churches while editing a Sermon's context.
- The app requests foreground precise location for that action, sends one coordinate pair to the authenticated backend, and does not retain the device fix.
- The backend validates the coordinates and delegates lookup through `ChurchSuggestionProvider`.
- The default Overpass adapter searches nearby Christian places of worship, identifies Pewcorder through a configured User-Agent, applies a bounded radius/result limit, and returns distance-ordered suggestions.
- Lookup alone persists nothing. The Congregant must confirm a suggestion before it becomes a reusable owner-private Church; its provider coordinates may then be stored on that Church.
- Permission denial, provider failure, or no results always leaves manual Church creation available.

## Consequences

Location enrichment remains post-capture and reversible, and a third-party place cannot silently become Sermon metadata. The public Overpass instance is suitable for modest development and early-product traffic; production can replace it through configuration if volume, availability, or terms require a dedicated provider.
