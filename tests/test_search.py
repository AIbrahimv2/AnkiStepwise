"""The tree's search: lax matching (parts of words, other endings, typos,
abbreviations), and Hide done leaving done topics out of the results."""
import json
import time

from harness import *  # noqa: F401,F403
from harness import actions
from tq import fuzzy
from tq.bridge import Bridge
from tq.state import COMPLETED
from aqt.qt import QWidget


class Host(QWidget):
    @property
    def index(self):
        return actions.cached_index()

    def request_index(self):
        actions.request_index(lambda i: None)

    def reload_index(self, force=False):
        if force:
            actions.mark_index_dirty()
        actions.request_index(lambda i: None)

    def push(self, e):
        pass


bridge = Bridge(Host())


def call(cmd, **a):
    r = bridge.handle(json.dumps({"cmd": cmd, **a}))
    assert "error" not in r, r
    return r


checks = 0


def check(ok, what):
    global checks
    assert ok, what
    checks += 1


def search(q):
    t = time.time()
    r = call("search", query=q)
    check(time.time() - t < 1.5, f"{q!r} took {time.time() - t:.2f}s")
    check(r["summary"]["count"] == len(r["matches"]), "the count is the matches")
    return r


def any_key(r, *parts):
    return any(all(p in k for p in parts) for k in r["matches"])


call("boot")
call("set_option", key="hideCompleted", value=False)

# Every word, anywhere in the path, but loosely.
r = search("childhood development")
check(any_key(r, "08_childhood_development"), r["matches"])
check(any_key(r, "child_development"), "child counts for childhood")
check(any_key(r, "developmental"), "developmental counts for development")
check(set(search("childhood and development")["matches"]) == set(r["matches"]), "little words are skipped")
check(any_key(search("development milestone"), "developmental_milestones"), "other endings")
typo = search("devlopment")
check(any_key(typo, "development"), "a typo")
check("development" in typo["terms"], f"the word it matched is highlighted: {typo['terms']}")
check(any_key(search("pyschiatry"), "psychiatry"), "swapped letters")
check(any_key(search("pregancy"), "pregnancy"), "a missing letter")
check(any_key(search("msk"), "musculoskeletal"), "an abbreviation")
check(any_key(search("musculoskeletal"), "::msk"), "and back")
check(any_key(search("peds"), "pediatric"), "peds")
check(any_key(search("b&b cardio"), "#b&b", "cardio"), "resource and topic")
check(not search("zzzzqqq")["matches"], "nothing for nonsense")

# Hide done: done topics aren't matches, so the count, the rows and n/N agree.
everything = search("childhood development")
view = bridge.view()
done = [k for k in everything["matches"] if view.status_of(k)[0] == COMPLETED]
check(done, "some matches are done (the test needs some)")
call("set_option", key="hideCompleted", value=True)
hidden = search("childhood development")
view = bridge.view()
check(not any(view.status_of(k)[0] == COMPLETED for k in hidden["matches"]), "no done matches")
check(set(hidden["matches"]) == set(everything["matches"]) - set(done), "only the done ones go")
check(hidden["summary"]["done"] == 0, hidden["summary"])
call("set_option", key="hideCompleted", value=False)

# The matcher's pieces.
check(fuzzy.within("pyschiatry", "psychiatry", 1), "a swap is one edit")
check(not fuzzy.within("cardiac", "renal", 2), "unrelated words")
check(fuzzy.query_words("Childhood and Development") == ["childhood", "development"], "words")
check(fuzzy.query_words("and of") == ["and", "of"], "only little words: keep them")
check(fuzzy.stem("developmental") == "development", fuzzy.stem("developmental"))
print(f"SEARCH TESTS PASSED ({checks} checks)")
