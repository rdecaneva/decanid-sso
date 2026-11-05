# decanID

A quiet chess identity for the shared sign-in service. The original geometric rook contains a keyhole; the ivory authentication form sits centered on the page, without a background illustration or sign-in slogan. The readable wordmark keeps the requested `decanID` casing.

Palette: ivory `#f6f4ed`, charcoal `#202823`, forest `#28533b`. Georgia/Times supplies the serif voice; the form uses system sans-serif. All assets are local SVGs, with no external font or image requests.

`decanid-wordmark.svg` is the horizontal identity, `decanid-rook.svg` is the standalone mark, `decanid-favicon.svg` is its small inverse version. The centered form adapts to desktop, tablet, and phone widths. `decanid.css` is applied through Authentik’s native brand field; no frontend bundle or authentication template is patched.

The design direction adapts the frontend skill’s framed-sheet composition to an existing authentication screen. It keeps the native fields, validation, password/MFA stages, locale control, and footer. Custom layout selectors are scoped to the login. The default authentication flow’s display title is blank; other flow titles remain intact.

Browser verification uses Playwright and inspects Authentik’s Shadow DOM at 1440×900, 768×1024, and 390×844. Before/after captures are in `.taste-skill/before` and `.taste-skill/after` (ignored by Git). Inputs and primary buttons increase from 36px to 50px; no horizontal overflow is present. Keyboard focus has a visible forest outline. Layout and imagery are static and reduced-motion preferences are honored.

The skill’s standalone inspector requires Node 22; the host has Node 18, so Playwright screenshots and direct computed-style checks provide the visual review. The skill lint reports no failures; its shadow warnings refer to explicit `box-shadow: none` declarations removing Authentik’s inherited card shadow.

Reapply with `docker compose exec -T server ak shell < scripts/configure-branding.py`. The first application backs up the prior settings to the persistent `/data/decanid-branding-backup.json`. Asset changes are served directly from the read-only Compose mount; CSS changes need the reapply command.

Login loading overlays use a transparent background. The native spinner and pointer blocking remain active during requests.

Email branding uses the same ivory/charcoal/forest palette and wordmark. The PNG wordmark is embedded inline as `cid:logo`; custom templates live in `templates/email`. Both server and worker mount the templates and PNG read-only. These templates cover verification, password reset, the transport test, and the shared base inherited by invitation/notification messages. Preview images are under `.taste-skill/email`.
