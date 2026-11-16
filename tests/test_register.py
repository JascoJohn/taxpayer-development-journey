"""The intervention register (the six stage tools of docs/interventions.yaml) has unique deterministic IDs and a second run does not change it."""
import json
import os
import re

from conftest import run_all, snapshot


def _load(project, rel):
    with open(os.path.join(project, rel), encoding="utf-8") as f:
        return json.load(f)


def test_register_has_6_unique_ids(project):
    assert run_all(project, "--clean").returncode == 0
    reg = _load(project, "outputs/stats/intervention_register.json")
    ids = [i["intervention_id"] for i in reg["interventions"]]
    assert reg["total"] == 6 == len(ids)
    assert len(set(ids)) == 6
    assert all(re.fullmatch(r"INT-[0-9A-F]{6}", x) for x in ids)
    for i in reg["interventions"]:
        assert "**" not in i["title"] and "created_at" not in i
    ctx = _load(project, "data/interim/shared_context.json")
    assert ctx["interventions"]["total_generated"] == 6
    in_ctx = {x for v in ctx["interventions"]["by_stage"].values() for x in v}
    assert in_ctx <= set(ids)


def test_second_run_does_not_change_register(project):
    assert run_all(project, "--clean").returncode == 0
    before = snapshot(project)
    assert run_all(project).returncode == 0          # no --clean: must not accumulate
    after = snapshot(project)
    assert before == after, [k for k in before if before[k] != after.get(k)]
    assert _load(project, "outputs/stats/intervention_register.json")["total"] == 6
