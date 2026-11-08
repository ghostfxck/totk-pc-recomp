"""Compare uniform-update paths using private copies of an existing Linux install.

This is an experimental investigation of issue #974, not a confirmed fix. Game-derived
files belong only in ignored build/ directories, never in the public fork.
"""
import argparse
import datetime
import os
from pathlib import Path
import shutil
import subprocess


def prepare(game, dest):
    if dest.exists():
        raise SystemExit(f'Refusing to replace an existing test directory: {dest}')
    dest.mkdir(parents=True)
    # Copies can use filesystem reflinks, but never hardlinks: mutable caches and
    # settings must not write through to the original install.
    for item in game.iterdir():
        if item.name in {'romfs', 'exefs'} or item.name.startswith('romfs-patches'):
            (dest / item.name).symlink_to(item, target_is_directory=item.is_dir())
        elif item.name in {'profile', 'shader-cache', 'mesa-cache', 'mods'} or item.is_file() and (
            item.name in {'totk', 'totk_xlate', 'totk_xlate.id', 'totk.ini'}
            or item.suffix == '.bin' or item.name.startswith(('libSDL', 'libnvidia-ngx'))
        ):
            subprocess.run(['cp', '--reflink=auto', '-aL', '--', str(item), str(dest / item.name)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-dir', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path, help='new private test directory; use build/ in a checkout')
    ap.add_argument('--exe', type=Path, help='candidate executable; otherwise use the installed executable')
    ap.add_argument('--case', choices=('stock', 'legacy'), required=True)
    a = ap.parse_args()
    game, dest = a.game_dir.resolve(), a.out.resolve()
    if not (game / 'totk').is_file() or not (game / 'profile').is_dir():
        ap.error('--game-dir must contain totk and profile/')
    if dest == game or game in dest.parents:
        ap.error('--out must be outside the original install')
    exe = a.exe.resolve() if a.exe else None
    if exe and not exe.is_file():
        ap.error('--exe does not exist')
    prepare(game, dest)
    if exe:
        shutil.copy2(exe, dest / 'totk')
    env = os.environ.copy()
    # Hold the reported recorder setting and frame limit equal between runs.
    # Both overlay variants include 0.3.13's outside-pass switch so overrides in
    # the user's ini cannot accidentally make both tests take the same path.
    overrides = dict(TOTK_UB_OVERLAY='0' if a.case == 'legacy' else '1',
                     TOTK_UB_OVERLAY_OUT='1', TOTK_VK_RECORDER='0', TOTK_REPLAY_ASYNC='0',
                     TOTK_FPS_LIMIT='144', TOTK_TRACE='perf,sched', TOTK_PERF_OVERLAY='full')
    env.update(overrides)
    log = dest / 'comparison.log'
    print(f'Opening {a.case} test. Load the same save, stand in the same spot for 60 seconds, then quit.', flush=True)
    print(f'Private test data and log: {dest}', flush=True)
    with log.open('w') as f:
        f.write(f'case={a.case}, time={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n')
        for k, v in sorted(overrides.items()):
            f.write(f'{k}={v}\n')
        f.flush()
        result = subprocess.run([str(dest / 'totk'), '--exefs', str(dest / 'exefs'),
                                 '--romfs', str(dest / 'romfs'), '--profile', str(dest / 'profile')],
                                cwd=dest, env=env, stdout=f, stderr=subprocess.STDOUT)
    print(f'Game exit code {result.returncode}; log: {log}')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
