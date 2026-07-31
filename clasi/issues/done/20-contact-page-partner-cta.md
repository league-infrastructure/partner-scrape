---
status: done
---

# Replace Donate button with partner-appropriate CTA on Contact Us page

## Description

Client feedback: the Contact Us page shows a "Donate" button in the
section aimed at prospective partners. Donations are appreciated, but
that is not the action being proposed to partners there — the CTA
should invite partnership/contact instead.

The client is wary of a button that auto-starts an email (mailto:)
with their address, since exposing the address could invite spam.

## Options to consider

- A contact form that posts to a form backend (e.g. the static-site
  form services: Formspree, Netlify Forms, Web3Forms, or similar) so
  no email address appears in the page source.
- A mailto: link with the address obfuscated (assembled by JavaScript
  at click time) — lighter weight, but weaker protection than a form.
- A shared/role alias (e.g. partners@...) behind either approach, so
  the personal address is never published and the alias can be rotated
  if it starts attracting spam.

## Acceptance

- The partner section of the Contact Us page no longer shows a Donate
  button as its primary CTA.
- Partners have a clear way to reach the organization that does not
  publish a personal email address in plain text in the page source.
