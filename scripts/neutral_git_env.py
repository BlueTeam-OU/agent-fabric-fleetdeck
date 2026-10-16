import os
from unittest import mock


def isolate_git(testcase):
    """Run a test's git children with no account git config.

    The account's own global and system config (commit and tag signing, its
    identity) must not reach a test that makes commits or tags in a temporary
    repository: a signing account would otherwise fail it. The environment is
    patched, so git children of the code under test are neutral as well.
    """
    patcher = mock.patch.dict(os.environ, {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "commit.gpgsign",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "tag.gpgsign",
        "GIT_CONFIG_VALUE_1": "false",
        "GIT_AUTHOR_NAME": "FleetDeck Test",
        "GIT_AUTHOR_EMAIL": "herdr@example.invalid",
        "GIT_COMMITTER_NAME": "FleetDeck Test",
        "GIT_COMMITTER_EMAIL": "herdr@example.invalid",
    })
    patcher.start()
    testcase.addCleanup(patcher.stop)
