# Linux NVIDIA performance experiment for issue #974

Status: an unverified fallback for testing, not a confirmed root-cause fix and not ready for an upstream PR.

Issue #974 reports that 0.3.11 runs much faster than 0.3.12 and 0.3.13 on Linux with an RTX 5060 Laptop GPU.
The submitted gameplay screenshot shows 26.3 ms frames, 12.60 ms GPU frame preparation, 4.06 ms GPU busy,
and no shader or pipeline waits. This points toward CPU-side work, but does not identify the responsible function.

Between 0.3.11 and 0.3.12, commit 9069c92 introduced uniform-update overlays. On a partial or unaligned match,
`runtime/vk_exec_draw.c`, `ub_bind` copies and merges the entire binding on the CPU, walks the submission's updates,
and prevents the next descriptor build from being skipped. This is a plausible source of extra CPU work; it has
**not** been measured as the cause on the reporter's laptop. Other changes in the same release remain suspects.

This branch defaults `ub_overlay` to `0` on Linux NVIDIA only. This restores immediate uniform updates while retaining
0.3.13's resource lifetime and other fixes. Other platforms and vendors keep their existing default. An explicit
`ub_overlay` / `TOTK_UB_OVERLAY` setting still wins. This is a fallback experiment, not an optimisation of the new path.
It can increase GPU barriers and reduce performance if the batching path was beneficial.

## Test without compiling

The installed 0.3.13 already has the required override. Use Python 3 on Linux:

```sh
python3 tools/test_linux_fps.py --game-dir '/path/to/totk' --out build/974-stock --case stock
python3 tools/test_linux_fps.py --game-dir '/path/to/totk' --out build/974-legacy --case legacy
```

The tool refuses to replace existing directories. Each test copies the profile, settings, executable, shader caches
and other mutable assets; large immutable game assets are linked read-only by convention. It does not modify the
original install. Allow several GiB of disk space if your filesystem cannot reflink the copies. Keep these private
files under ignored `build/`; do not upload the test directories or executables to GitHub.

To test a locally compiled candidate, pass `--exe /path/to/candidate/totk`. Both cases deliberately use explicit
overlay settings so the same executable can run either path.

Load the same save, face the same direction, wait for loading to settle, and stand still for at least 60 seconds.
Close the game between runs. Repeat stock after legacy to check for changes caused by temperature or clock speed.
Run on mains power with the same laptop power profile. Compare the gameplay portion of `comparison.log`, especially
FPS, replay time, GPU busy and the uniform-update statistics. Title-screen FPS alone is insufficient.

If legacy recovers performance, attach both logs and exact settings to #974 before proposing a narrowly scoped fix.
If it does not, this fallback should not be proposed upstream; investigate the other 0.3.12 changes next.

## Validation limits

The agent environment does not expose `/dev/dri` or `/dev/nvidia*`. An attempted isolated gameplay run stopped with
`no usable Vulkan device`, so neither gameplay correctness nor an FPS improvement has been verified here.
The runtime and selftest can be built without uploading any game-derived files.

## Checks run for this candidate

- Linux runtime archive compiled and linked against the install's unchanged generated objects.
- `totk --selftest`: passed, zero failures.
- `totk --probe-cfg`: passed.
- `python3 tests/linux_fps_launcher_test.py`: passed; checks overrides, save/cache isolation including symlinks,
  and refusal to overwrite existing or nested test directories.
- `git diff --check`: passed.
- `python3 tests/settings_doc_check.py`: fails on the pre-existing undocumented `DESWIZZLE` setting in upstream
  0.3.13; no new setting is introduced by this experiment.

The locally linked executable contains private game-derived code and is not committed or uploaded.
