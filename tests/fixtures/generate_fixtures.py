"""Deterministic generator for the offline test fixtures.

Run ``python tests/fixtures/generate_fixtures.py`` to (re)write the JSON
files next to this script. The data is fully synthetic — fictional player
names, scripted scores — but matches the exact row shapes Buzzer's
``CachedSource`` stores from the live nba_api endpoints.

Two games are produced:

* ``0042500401`` — a synthetic Finals game. The home side trails by 13 in
  the third quarter and wins 101-100 on a 27-foot three with one second
  left. This exercises every detection rule: clutch time, lead change,
  comeback, playoff flag, distance.
* ``0022500123`` — a quiet regular-season blowout that must yield no
  moments at the default threshold.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).parent

# (clock, side, points, shot_distance_ft) — points 0 = missed FG,
# 1 = made free throw, 2/3 = made field goal.
Play = tuple[str, str, int, int | None]

HOME_NAMES = ["Z. Fakesmith", "T. Mockwell"]
AWAY_NAMES = ["Q. Testman", "R. Samplevich"]
DIST_2PT = [2, 5, 9, 16, 19]
DIST_3PT = [24, 25, 26]
ANGLES_DEG = [-55, -30, -10, 10, 30, 55]


def _clock_parts(clock: str) -> tuple[int, int]:
    minutes, _, seconds = clock.partition(":")
    return int(minutes), int(seconds)


class GameBuilder:
    def __init__(self, game_id: str, home: str, away: str, date_iso: str) -> None:
        self.game_id = game_id
        self.home = home
        self.away = away
        self.date_iso = date_iso
        self.rows: list[dict[str, Any]] = []
        self.shots: list[dict[str, Any]] = []
        self.home_score = 0
        self.away_score = 0
        self._ev = 2
        self._n2 = 0
        self._n3 = 0
        self._angle = 0
        self._name = 0

    def _next_ev(self) -> int:
        ev = self._ev
        self._ev += 3
        return ev

    def _row(
        self,
        event_type: int,
        period: int,
        clock: str,
        home_desc: str | None = None,
        neutral_desc: str | None = None,
        visitor_desc: str | None = None,
        with_score: bool = False,
        tricode: str | None = None,
        player: str | None = None,
        action_type: int = 0,
    ) -> dict[str, Any]:
        margin = self.home_score - self.away_score
        row = {
            "GAME_ID": self.game_id,
            "EVENTNUM": self._next_ev(),
            "EVENTMSGTYPE": event_type,
            "EVENTMSGACTIONTYPE": action_type,
            "PERIOD": period,
            "WCTIMESTRING": "9:00 PM",
            "PCTIMESTRING": clock,
            "HOMEDESCRIPTION": home_desc,
            "NEUTRALDESCRIPTION": neutral_desc,
            "VISITORDESCRIPTION": visitor_desc,
            "SCORE": f"{self.away_score} - {self.home_score}" if with_score else None,
            "SCOREMARGIN": ("TIE" if margin == 0 else str(margin)) if with_score else None,
            "PLAYER1_NAME": player,
            "PLAYER1_TEAM_ABBREVIATION": tricode,
        }
        self.rows.append(row)
        return row

    def _shot_row(
        self,
        event_num: int,
        period: int,
        clock: str,
        dist: int,
        made: bool,
        is_three: bool,
        player: str,
        tricode: str,
    ) -> None:
        angle = math.radians(ANGLES_DEG[self._angle % len(ANGLES_DEG)])
        self._angle += 1
        minutes, seconds = _clock_parts(clock)
        self.shots.append(
            {
                "GRID_TYPE": "Shot Chart Detail",
                "GAME_ID": self.game_id,
                "GAME_EVENT_ID": event_num,
                "PLAYER_ID": 9990000 + (self._angle % 4),
                "PLAYER_NAME": player,
                "TEAM_ID": 16100 if tricode == self.home else 16200,
                "TEAM_NAME": "Home Club" if tricode == self.home else "Away Club",
                "PERIOD": period,
                "MINUTES_REMAINING": minutes,
                "SECONDS_REMAINING": seconds,
                "EVENT_TYPE": "Made Shot" if made else "Missed Shot",
                "ACTION_TYPE": "Jump Shot",
                "SHOT_TYPE": "3PT Field Goal" if is_three else "2PT Field Goal",
                "SHOT_ZONE_BASIC": "Above the Break 3" if is_three else "Mid-Range",
                "SHOT_DISTANCE": dist,
                "LOC_X": round(dist * 10 * math.sin(angle)),
                "LOC_Y": round(dist * 10 * math.cos(angle)),
                "SHOT_ATTEMPTED_FLAG": 1,
                "SHOT_MADE_FLAG": 1 if made else 0,
                "GAME_DATE": self.date_iso.replace("-", ""),
                "HTM": self.home,
                "VTM": self.away,
            }
        )

    def _pick_name(self, side: str) -> str:
        names = HOME_NAMES if side == "H" else AWAY_NAMES
        self._name += 1
        return names[self._name % len(names)]

    def _pick_dist(self, points: int) -> int:
        if points == 3:
            self._n3 += 1
            return DIST_3PT[self._n3 % len(DIST_3PT)]
        self._n2 += 1
        return DIST_2PT[self._n2 % len(DIST_2PT)]

    def add_quarter(self, period: int, plays: list[Play]) -> None:
        self._row(12, period, "12:00", neutral_desc="Start of Period")
        for clock, side, points, dist in plays:
            name = self._pick_name(side)
            tricode = self.home if side == "H" else self.away
            if points == 0:
                self._add_miss(period, clock, side, dist, name, tricode)
            elif points == 1:
                self._add_free_throw(period, clock, side, name, tricode)
            else:
                self._add_field_goal(period, clock, side, points, dist, name, tricode)
        self._row(13, period, "0:00", neutral_desc="End of Period")

    def _add_field_goal(
        self,
        period: int,
        clock: str,
        side: str,
        points: int,
        dist: int | None,
        name: str,
        tricode: str,
    ) -> None:
        if dist is None:
            dist = self._pick_dist(points)
        if side == "H":
            self.home_score += points
        else:
            self.away_score += points
        desc = f"{name} {dist}' {'3PT ' if points == 3 else ''}Jump Shot"
        row = self._row(
            1,
            period,
            clock,
            home_desc=desc if side == "H" else None,
            visitor_desc=desc if side == "A" else None,
            with_score=True,
            tricode=tricode,
            player=name,
            action_type=1,
        )
        self._shot_row(row["EVENTNUM"], period, clock, dist, True, points == 3, name, tricode)

    def _add_free_throw(self, period: int, clock: str, side: str, name: str, tricode: str) -> None:
        if side == "H":
            self.home_score += 1
        else:
            self.away_score += 1
        desc = f"{name} Free Throw 1 of 1"
        self._row(
            3,
            period,
            clock,
            home_desc=desc if side == "H" else None,
            visitor_desc=desc if side == "A" else None,
            with_score=True,
            tricode=tricode,
            player=name,
        )

    def _add_miss(
        self, period: int, clock: str, side: str, dist: int | None, name: str, tricode: str
    ) -> None:
        if dist is None:
            dist = self._pick_dist(2)
        desc = f"MISS {name} {dist}' Jump Shot"
        row = self._row(
            2,
            period,
            clock,
            home_desc=desc if side == "H" else None,
            visitor_desc=desc if side == "A" else None,
            tricode=tricode,
            player=name,
            action_type=1,
        )
        self._shot_row(row["EVENTNUM"], period, clock, dist, False, dist >= 22, name, tricode)
        rebounder_side = "A" if side == "H" else "H"
        rebound_name = self._pick_name(rebounder_side)
        rebound_desc = f"{rebound_name} REBOUND"
        self._row(
            4,
            period,
            clock,
            home_desc=rebound_desc if rebounder_side == "H" else None,
            visitor_desc=rebound_desc if rebounder_side == "A" else None,
            tricode=self.home if rebounder_side == "H" else self.away,
            player=rebound_name,
        )


# ---------------------------------------------------------------------------
# Game 1: synthetic Finals game 0042500401 — BOS 101, DEN 100.
# Home trails by 13 in Q3, wins on a 27-foot three with 0:01 left.
# ---------------------------------------------------------------------------

FINALS_Q1: list[Play] = [
    ("11:40", "A", 3, None),
    ("11:15", "H", 2, None),
    ("10:50", "A", 2, None),
    ("10:22", "H", 3, None),
    ("10:05", "H", 0, None),
    ("9:58", "A", 2, None),
    ("9:31", "H", 2, None),
    ("9:05", "A", 3, None),
    ("8:40", "H", 3, None),
    ("8:12", "A", 2, None),
    ("7:47", "H", 2, None),
    ("7:20", "A", 2, None),
    ("7:05", "A", 0, None),
    ("6:55", "H", 3, None),
    ("6:30", "A", 3, None),
    ("6:02", "H", 1, None),
    ("6:01", "H", 1, None),
    ("5:38", "A", 2, None),
    ("5:11", "H", 2, None),
    ("4:45", "A", 3, None),
    ("4:32", "H", 0, None),
    ("4:20", "H", 2, None),
    ("3:52", "A", 2, None),
    ("3:27", "H", 3, None),
    ("3:00", "A", 3, None),
]
FINALS_Q2: list[Play] = [
    ("11:30", "A", 2, None),
    ("11:05", "H", 2, None),
    ("10:38", "A", 3, None),
    ("10:12", "H", 2, None),
    ("9:50", "A", 2, None),
    ("9:25", "H", 3, None),
    ("9:02", "A", 2, None),
    ("8:55", "H", 0, None),
    ("8:40", "H", 2, None),
    ("8:15", "A", 3, None),
    ("7:52", "H", 1, None),
    ("7:51", "H", 1, None),
    ("7:30", "A", 2, None),
    ("6:42", "A", 2, None),
    ("6:15", "H", 2, None),
    ("5:55", "A", 3, None),
    ("5:30", "H", 2, None),
    ("5:08", "A", 2, None),
    ("4:45", "H", 3, None),
    ("4:32", "A", 0, None),
    ("4:20", "A", 2, None),
    ("3:58", "H", 3, None),
    ("3:32", "A", 3, None),
    ("2:45", "A", 2, None),
]
FINALS_Q3: list[Play] = [
    ("10:40", "A", 3, None),  # away up 13 — the comeback baseline
    ("10:05", "H", 3, None),
    ("9:38", "H", 2, None),
    ("9:25", "A", 0, None),
    ("9:10", "A", 2, None),
    ("8:44", "H", 3, None),
    ("8:15", "H", 2, None),
    ("7:50", "A", 2, None),
    ("7:22", "H", 2, None),
    ("6:55", "A", 3, None),
    ("6:30", "H", 2, None),
    ("6:05", "H", 1, None),
    ("6:04", "H", 1, None),
    ("5:40", "A", 2, None),
    ("5:12", "H", 3, None),
    ("4:46", "A", 2, None),
    ("4:20", "H", 3, None),
    ("3:55", "A", 2, None),
    ("3:28", "H", 3, None),
    ("3:02", "A", 3, None),
    ("2:35", "A", 2, None),
    ("2:10", "H", 0, None),
]
FINALS_Q4: list[Play] = [
    ("11:35", "H", 2, None),
    ("11:10", "A", 2, None),
    ("10:42", "H", 3, None),
    ("10:15", "A", 2, None),
    ("10:00", "A", 0, None),
    ("9:50", "H", 2, None),
    ("9:22", "A", 3, None),
    ("8:55", "H", 2, None),
    ("8:30", "H", 3, None),
    ("8:02", "A", 2, None),
    ("7:36", "H", 2, None),
    ("7:10", "A", 2, None),
    ("6:44", "H", 1, None),
    ("6:43", "H", 1, None),
    ("6:15", "A", 2, None),
    ("5:48", "H", 2, None),
    ("5:20", "A", 3, None),
    ("4:55", "H", 2, None),
    ("4:31", "H", 2, None),  # ties it at 92
    ("4:05", "A", 2, None),
    ("3:40", "H", 2, None),  # ties it at 94
    ("3:12", "A", 3, None),
    ("2:45", "H", 2, None),
    ("2:20", "A", 2, None),
    ("1:40", "H", 0, None),
    ("1:05", "A", 1, None),
    ("0:33", "H", 2, None),
    ("0:19", "A", 0, 26),
    ("0:01", "H", 3, 27),  # the moment: go-ahead 27-footer, one second left
]
FINALS_QUARTER_TOTALS = [(24, 27), (45, 55), (70, 76), (101, 100)]  # (home, away)


# ---------------------------------------------------------------------------
# Game 2: quiet regular-season game 0022500123 — MIN 98, UTA 83. No drama.
# ---------------------------------------------------------------------------


def quiet_quarter(extra_home: bool = False, extra_away: bool = False) -> list[Play]:
    home_pts = [3, 2, 3, 2, 3, 2, 3, 2, 2, 2] + ([2] if extra_home else [])
    away_pts = [2, 3, 2, 2, 3, 2, 2, 2, 2] + ([3] if extra_away else [])
    plays: list[Play] = []
    seconds = 11 * 60 + 40
    h, a = 0, 0
    while h < len(home_pts) or a < len(away_pts):
        for side in ("H", "A"):
            pts_list = home_pts if side == "H" else away_pts
            idx = h if side == "H" else a
            if idx < len(pts_list):
                plays.append((f"{seconds // 60}:{seconds % 60:02d}", side, pts_list[idx], None))
                seconds -= 35
                if side == "H":
                    h += 1
                else:
                    a += 1
    return plays


def build_finals_game() -> GameBuilder:
    game = GameBuilder("0042500401", home="BOS", away="DEN", date_iso="2026-06-04")
    for period, plays, totals in zip(
        range(1, 5),
        [FINALS_Q1, FINALS_Q2, FINALS_Q3, FINALS_Q4],
        FINALS_QUARTER_TOTALS,
        strict=True,
    ):
        game.add_quarter(period, plays)
        actual = (game.home_score, game.away_score)
        assert actual == totals, f"Q{period} totals {actual} != expected {totals}"
    return game


def build_quiet_game() -> GameBuilder:
    game = GameBuilder("0022500123", home="MIN", away="UTA", date_iso="2025-11-05")
    game.add_quarter(1, quiet_quarter())
    game.add_quarter(2, quiet_quarter())
    game.add_quarter(3, quiet_quarter())
    game.add_quarter(4, quiet_quarter(extra_home=True, extra_away=True))
    assert (game.home_score, game.away_score) == (98, 83), (
        game.home_score,
        game.away_score,
    )
    return game


def summary(game: GameBuilder, season: str, cities: tuple[str, str]) -> dict[str, Any]:
    return {
        "game_id": game.game_id,
        "game_date": game.date_iso,
        "season": season,
        "is_playoff": game.game_id.startswith("004"),
        "home_tricode": game.home,
        "away_tricode": game.away,
        "home_city": cities[0],
        "away_city": cities[1],
    }


def _write(name: str, payload: Any) -> None:
    path = OUT_DIR / name
    with path.open("w") as f:
        json.dump(payload, f, indent=1)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> None:
    finals = build_finals_game()
    quiet = build_quiet_game()
    finals_summary = summary(finals, "2025-26", ("Boston", "Denver"))
    quiet_summary = summary(quiet, "2025-26", ("Minneapolis", "Salt Lake City"))

    _write("pbp_0042500401.json", finals.rows)
    _write("shots_0042500401.json", finals.shots)
    _write("summary_0042500401.json", finals_summary)
    _write("pbp_0022500123.json", quiet.rows)
    _write("shots_0022500123.json", quiet.shots)
    _write("summary_0022500123.json", quiet_summary)
    _write("games_2025-26_playoffs.json", [finals_summary])


if __name__ == "__main__":
    main()
