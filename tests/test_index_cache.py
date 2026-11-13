"""The tag index saved between sessions: startup reads it instead of
counting, treats it as out of date, and rebuilds later (never at startup).
Also the "Syncing" signals, and the deck meter asking for a rebuild."""
import os
import pickle
import time

from harness import *  # noqa: F401,F403
from harness import FIXTURE, actions, col, mw

from tq import counts, index_cache, widget

n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


# Save to the test's own folder, not the add-on's.
index_cache.USER_FILES = os.path.join(FIXTURE, "work", "user_files")
mode = actions.get_config()["count_mode"]
path = index_cache.path_for(col.path)
if os.path.exists(path):
    os.unlink(path)

# --- the first session: nothing saved, so it's counted (and saved) --------------

check(not actions.load_saved_index(), "nothing saved yet")
events = []
actions.on_building(events.append)
actions.request_index()
built = actions.cached_index()
check(events == [True, False], f"rebuilds say when they start and stop ({events})")
check(os.path.exists(path), "the first build of a session is saved, for the next")
first_saved = os.path.getmtime(path)

# --- the next session: read, not counted -----------------------------------------

actions.reset()
calls = []
real_build = counts.build_index
actions.build_index = lambda *a: calls.append(1) or real_build(*a)
t = time.perf_counter()
check(actions.load_saved_index(), "next session, the saved index is read")
took = (time.perf_counter() - t) * 1000
idx = actions.cached_index()
check(idx is not built and idx.names == built.names and idx.card_ids == built.card_ids
      and idx.fresh == built.fresh and idx.tag_cards == built.tag_cards, "and it's the same index")
check(not calls, "nothing is counted at startup")
check(actions.index_stale() and actions._membership_dirty, "it counts as out of date, membership included")
print(f"  read in {took:.0f} ms")

# Out of date means checking a topic off asks Anki which cards are under it.
searched = []
real_suspended = actions.suspended_ids
actions.suspended_ids = lambda c, tags: searched.append(tags) or real_suspended(c, tags)
some = next(k for k in idx.post_order if k.count("::") >= 3 and idx.total.get(k, 0) > 5)
actions.suspended_cards([idx.name(some)])
check(searched, "until it's rebuilt, which cards are under a tag comes from Anki's search")
actions.suspended_ids = real_suspended

actions.request_index()
check(len(calls) == 1 and actions.cached_index() is not idx and not actions.index_stale(), "asking for it rebuilds it")
actions.build_index = real_build

# --- saving: only what's new, and only good files are read ------------------------

actions.save_index()
check(os.path.getmtime(path) >= first_saved, "a rebuilt index is saved again at the end of a session")
mtime = os.path.getmtime(path)
time.sleep(0.01)
actions.save_index()
check(os.path.getmtime(path) == mtime, "and not when nothing was rebuilt since")
check(index_cache.load(col.path, "all" if mode != "all" else "new") is None, "an index counted another way isn't used")

good = open(path, "rb").read()
open(path, "wb").write(b"not a pickle")
check(index_cache.load(col.path, mode) is None, "a damaged file is ignored")
open(path, "wb").write(pickle.dumps({"format": index_cache.FORMAT + 1, "fields": {}}))
check(index_cache.load(col.path, mode) is None, "so is one from another version")


class Evil:
    def __reduce__(self):
        return (os.system, ("touch " + os.path.join(FIXTURE, "work", "pwned"),))


open(path, "wb").write(pickle.dumps({"format": index_cache.FORMAT, "fields": Evil()}))
check(index_cache.load(col.path, mode) is None, "a tampered file is refused")
check(not os.path.exists(os.path.join(FIXTURE, "work", "pwned")), "without running anything")
open(path, "wb").write(good)

# --- the deck meter: a rebuild, later, never during startup ------------------------

asked = []
real_later = actions.refresh_index_later
actions.refresh_index_later = lambda cb=None: asked.append(cb)
actions.mark_index_dirty()
widget._data()
check(asked == [widget.update_in_place], "a meter showing out-of-date counts asks for a rebuild")
asked.clear()
actions.request_index()
widget._data()
check(not asked, "and doesn't once they're current")
actions.refresh_index_later = real_later

actions._opened_at = time.monotonic()
actions.refresh_index_later()
wait = actions._later_timer.interval()
check(wait >= (actions.STARTUP_GRACE - 1) * 1000, f"right after startup it waits out the startup ({wait} ms)")
actions._opened_at = time.monotonic() - 60
actions.refresh_index_later()
check(actions._later_timer.interval() == actions.REFRESH_DELAY_MS, "later, it waits a moment, for a burst of changes")
actions._later_timer.stop()

actions.mark_index_dirty()
ran = []
mw.state = "review"
actions._later_callbacks[:] = [lambda: ran.append(1)]
actions._refresh_now()
check(actions.index_stale() and not ran, "not while you're reviewing: the next deck screen asks again")
mw.state = "deckBrowser"
actions._later_callbacks[:] = [lambda: ran.append(1)]
actions._refresh_now()
check(not actions.index_stale() and ran == [1], "on the deck screen it rebuilds and the meter updates")
actions.off_building(events.append)
print(f"ok ({n} checks)")
