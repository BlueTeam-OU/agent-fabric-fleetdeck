"""The update manifests offer only FleetDeck's own release binaries.

distribution/latest.json and preview.json are what `agent-fabric-fleetdeck
update` and the installers read. Upstream's preview workflow writes Herdr's
preview builds into preview.json's `builds`, and an upstream sync merges
that entry in cleanly: the updater falls back to `builds[<build_id>].assets`,
so a Herdr download URL there would install Herdr as FleetDeck (sync #27's
review, P1). Every asset URL must be one of FleetDeck's releases.
"""

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFESTS = ("distribution/latest.json", "distribution/preview.json")
FLEETDECK_RELEASES = "https://github.com/BlueTeam-OU/agent-fabric-fleetdeck/releases/download/"


def asset_urls(node, path="$"):
    """(json path, url) of every asset's `url`, wherever an `assets` object sits."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key == "assets" and isinstance(value, dict):
                for name, asset in value.items():
                    url = asset.get("url") if isinstance(asset, dict) else None
                    yield f"{here}.{name}", url
            else:
                yield from asset_urls(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from asset_urls(value, f"{path}[{i}]")


class DistributionOffersFleetDeckOnly(unittest.TestCase):
    def test_every_asset_url_is_a_fleetdeck_release(self):
        for manifest in MANIFESTS:
            doc = json.loads((ROOT / manifest).read_text(encoding="utf-8"))
            for where, url in asset_urls(doc):
                with self.subTest(manifest=manifest, asset=where):
                    self.assertIsInstance(url, str)
                    self.assertTrue(url.startswith(FLEETDECK_RELEASES),
                                    f"{manifest} {where} offers {url}, not a FleetDeck release")

    def test_the_walk_finds_assets_under_builds_too(self):
        doc = {"assets": {}, "builds": {"b": {"assets": {"linux-x86_64": {"url": "https://example/x"}}}}}
        self.assertEqual(list(asset_urls(doc)), [("$.builds.b.assets.linux-x86_64", "https://example/x")])


if __name__ == "__main__":
    unittest.main()
