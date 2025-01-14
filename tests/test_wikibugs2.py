# encoding: utf-8
import queue
import json
import pytest
import requests

import configfetcher
import wikibugs
from tests.common import root
realconfigfile = root / "config.json"
mockconfigfile = root / "config.json.example"


@pytest.fixture()
def mockbugs():
    return wikibugs.Wikibugs2(
        configfetcher.ConfigFetcher(str(mockconfigfile))
    )


@pytest.fixture()
def realbugs():
    return wikibugs.Wikibugs2(
        configfetcher.ConfigFetcher(str(realconfigfile))
    )


def test_offline_scrape(mockbugs):
    content = (root / "tests" / "data" / "T87834").open(encoding="utf-8").read()

    tags = mockbugs.get_tags(content)

    assert {
        'Wikimedia-Fundraising',
        'Fundraising Tech Backlog',
        'Wikimedia-Fundraising-CiviCRM',
        '§ Fundraising Sprint Devo',
        'Fr-tech-archived-from-FY-2014/15',
    } == tags.keys()

    assert {'shade', 'disabled', 'uri', 'tagtype'} == tags['§ Fundraising Sprint Devo'].keys()
    assert tags['§ Fundraising Sprint Devo']['shade'] == 'blue'
    assert tags['§ Fundraising Sprint Devo']['disabled']
    assert tags['§ Fundraising Sprint Devo']['uri'] == '/tag/§_fundraising_sprint_devo/'
    assert tags['§ Fundraising Sprint Devo']['tagtype'] == 'calendar'


def test_online_scrape(mockbugs):
    content = requests.get('https://phabricator.wikimedia.org/T87834').text

    tags = mockbugs.get_tags(content)

    assert len(tags) > 0

    n_disabled = 0
    n_briefcase = 0
    n_calendar = 0

    for tag, props in tags.items():
        if props['disabled']:
            n_disabled += 1
        if props['tagtype'] == 'briefcase':
            n_briefcase += 1
        if props['tagtype'] == 'calendar':
            n_calendar += 1

    assert n_disabled > 0
    assert n_briefcase > 0


@pytest.mark.skipif(not realconfigfile.exists(), reason="Requires live site access")
class TestParseEvents:
    @pytest.fixture(autouse=True)
    def setup_bugs(self, realbugs):
        self.bugs = realbugs

    def _process(self, event):
        self.bugs.rqueue = queue.Queue()
        event = json.load((root / "tests" / "data" / "phab_events" / event).open())
        self.bugs.process_event(event)
        return list(self.bugs.rqueue.queue)

    def test_add_token(self):
        messages = self._process("token.json")
        assert len(messages) == 0

    def test_add_project(self):
        messages = self._process("addproject.json")
        assert len(messages) == 1
        message = messages[0]

        assert message['url'] == 'https://phabricator.wikimedia.org/T163142'  # no deeplink found
        assert 'comment' not in message

    def test_many_changes(self):
        messages = self._process("manychanges.json")
        assert len(messages) == 1
        message = messages[0]

        assert 'priority' in message
        assert 'old' in message['priority']
        assert 'new' in message['priority']
