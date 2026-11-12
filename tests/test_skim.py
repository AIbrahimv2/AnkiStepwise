"""Skim, the card browser add-on: p on a topic opens it on the topic's
cards, taken from the index; moving to another topic follows, only while
Skim shows Stepwise's cards. A stand-in for Skim's API records the calls."""
import json

from harness import *  # noqa: F401,F403
import harness
from harness import actions, col, mw

from aqt.qt import QWidget
from tq import skim_link
from tq.bridge import Bridge
from tq.counts import tags_search


class Host(QWidget):
    index = None

    def request_index(self):
        actions.request_index(self._set)

    def reload_index(self, force=False):
        self.request_index()

    def _set(self, i):
        self.index = i

    def push(self, e):
        pass


host = Host()
bridge = Bridge(host)


def call(cmd, **args):
    return bridge.handle(json.dumps({"cmd": cmd, **args}))


n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


class FakeSkim:
    def __init__(self):
        self.opened, self.followed, self.showing = [], [], None

    def open(self, *, search, card_ids, title, source):
        self.opened.append((search, card_ids, title, source))
        self.showing = source

    def following(self, source):
        return self.showing == source

    def follow(self, *, search, card_ids, title, source):
        self.followed.append((search, card_ids, title, source))


# Without Skim nothing changes.
check(not hasattr(mw, "skim"), "no Skim to start with")
check(call("boot")["skim"] is False, "the page hears Skim isn't there")
check("error" in call("preview", key="#ak_step1_v12::#b&b"), "p without Skim says so")
check("details" in call("details", key="#ak_step1_v12::#b&b"), "details work as before")
harness.BROWSED.clear()
call("browse", tags=["#AK_Step1_v12::#B&B"], skim=True)
check(len(harness.BROWSED) == 1, "b without Skim opens Anki's browser")

host.request_index()
index = host.index
check(index is not None, "index built")

# A topic with a few hundred cards.
topic = next(k for k in index.post_order if k.count("::") >= 3 and 50 <= index.total.get(k, 0) <= 400)
tag = index.name(topic)

mw.skim = skim = FakeSkim()
check(call("boot")["skim"] is True, "the page hears Skim is installed")
check("error" not in call("preview", key=topic), "p opens Skim")
search, ids, title, source = skim.opened[-1]
check(source == "Stepwise", "as Stepwise")
check(search == tags_search(col, [tag]), f"with the topic's search ({search})")
check(sorted(ids) == sorted(col.find_cards(search)), "and exactly the cards that search finds, from the index")
check(title == skim_link.short_name(tag.rsplit("::", 1)[-1]), f"named like the side panel names it ({title})")

other = next(k for k in index.post_order if k != topic and k.count("::") >= 3 and 20 <= index.total.get(k, 0) <= 400)
call("details", key=other)
check(len(skim.followed) == 1 and skim.followed[0][2] == skim_link.short_name(index.last(other)),
      "moving to another topic shows its cards in Skim")
check(sorted(skim.followed[0][1]) == sorted(col.find_cards(skim.followed[0][0])), "the right cards")

# b prefers Skim; B (no "skim") always means Anki's browser.
opened, browsed = len(skim.opened), len(harness.BROWSED)
call("browse", tags=[tag], skim=True)
check(len(skim.opened) == opened + 1 and len(harness.BROWSED) == browsed, "b opens Skim when it's installed")
check(sorted(skim.opened[-1][1]) == sorted(col.find_cards(skim.opened[-1][0])), "on the topic's cards")
call("browse", tags=[tag])
check(len(skim.opened) == opened + 1 and len(harness.BROWSED) == browsed + 1, "B opens Anki's browser even so")

# The queue panel: p on a resource's row opens all its topics, and its
# cursor is followed like the tree's selection.
check("error" not in call("preview", tags=[topic, other], title="Pixorize"), "p on a resource's row")
search2, ids2, title2, _ = skim.opened[-1]
check(title2 == "Pixorize", "named after the resource")
check(sorted(ids2) == sorted(col.find_cards(search2)), "with every one of its topics' cards")
call("follow", tags=[topic])
check(skim.followed[-1][2] == skim_link.short_name(index.last(topic)), "the queue's cursor is followed")

skim.showing = "something else"  # searched for something else in Skim
followed = len(skim.followed)
call("details", key=topic)
call("follow", tags=[other])
check(len(skim.followed) == followed, "no following once Skim shows other cards")

del mw.skim
call("details", key=other)
check(True, "and nothing breaks if Skim goes away")
print(f"ok ({n} checks)")
