---
role: "rust-ui-dev"
class: workflow
topic: "relayed-visual-spec-confirm"
description: "A visual or interaction spec the coordinator relays from the owner has been misread twice; before building, restate what is coloured/shown and confirm it against the owner's own words"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 8d2bb85e9e9a2ed2
---

## A visual or interaction spec the coordinator relays from the owner has been misread twice; before building, restate what is coloured/shown and confirm it against the owner's own words

A UI request reaches me through fabric-coordinator, which paraphrases the owner.
The paraphrase has changed the design twice on the FleetDeck tab rows:
- REQUEST 01a13fb9 read "a second row of tabs" as "more panes"; a fourth pane was
  built (#33) and then superseded by REQUEST 01a14132.
- REQUEST 01a14132 read "a second row of tab ... in yellow background" as the
  row's colour; #36 shipped a yellow row, and REQUEST 01a14306 corrected it:
  "yellow background was for selected tab".
Both times, the owner's own words were in the request and could be read either way.

**Why:** every misreading cost a merged PR, a rebuild of the owner's deck and a
second PR. A plan reply would have caught both before any code was written.

**How to apply:** when a relayed request specifies what a person sees, quote the
owner's words in the plan reply. Restate each visual property as "<element>: <property>"
(for example, "the row: tab-bar background; the selected sub-tab: yellow"), name the
reading you chose where the words allow two, and build only after the coordinator
confirms it with the owner. Related: [[deck-pane-tabs-j18]], [[tab-rows-config-j21]].

*References: deck-pane-tabs-j18, tab-rows-config-j21*

*Anchors: `src/config/model.rs::pane_tab_selected_bg`*

*Observed 2026-10-18 (rust-ui-dev)*
