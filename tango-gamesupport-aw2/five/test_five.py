#!/usr/bin/env python3
"""Tests for the map pipeline: python3 -m unittest five/test_five.py   (from tango-gamesupport-aw2/, or `aw2dev test --python`).
No ROM needed. They guard what Phase B (content kits) relies on: re-drawing maps never drops one, ids are unique and from the pool, the
data area has room."""
import os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map as mappy  # noqa: E402
import mapsfile  # noqa: E402

SRC = os.path.join(HERE, '..', 'src')


def rust_const(path, name):
    m = re.search(r'(?:pub(?:\(crate\))? )?const %s: [\w:<>, \[\]]+ = ([^;]+);' % name, open(os.path.join(SRC, path)).read())
    return m.group(1).strip() if m else None


class Merge(unittest.TestCase):
    def test_merge_keeps_every_existing_map(self):
        old = 'x\nmap A\narmies 5 9 1 2 3 4 5\nrow\n\nmap B\nbbb\n\nmap C\nccc\n'
        gen = 'map B\nnew-b\n\nmap D\nddd\n'
        out = mapsfile.merge(old, gen)
        names = [n for n, _ in mapsfile.split_blocks(out)]
        self.assertEqual(names, ['A', 'B', 'C', 'D'])
        blocks = dict(mapsfile.split_blocks(out))
        self.assertIn('new-b', blocks['B'])
        self.assertIn('ccc', blocks['C'])

    def test_design_maps_keeps_hand_made_maps(self):
        before = open(os.path.join(HERE, 'maps.txt')).read()
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'maps.txt')
            # an extra map that no generator draws, and a changed Pentagon Atoll: both must survive a re-draw
            extra = '\nmap Hand Made Test Map\narmies 2 3 1 2\nunits 1 1\n1.~\n~.2\n'
            open(path, 'w').write(before + extra)
            env = dict(os.environ, FIVE_MAPS_TXT=path)
            r = subprocess.run([sys.executable, os.path.join(HERE, 'design_maps.py')], env=env, cwd=HERE, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            after = dict(mapsfile.split_blocks(open(path).read()))
            old = dict(mapsfile.split_blocks(before))
            self.assertEqual(set(after), set(old) | {'Hand Made Test Map'})
            self.assertEqual(after['Pentagon Atoll'], old['Pentagon Atoll'])
            self.assertIn('1.~', after['Hand Made Test Map'])
        finally:
            shutil.rmtree(tmp)


class RiverPhase(unittest.TestCase):
    """A straight east-west river run is drawn in the phase of the bend it leaves (the games' 0x58 -> 0x39 -> 0x7B and 0x78 -> 0x19 -> 0x5B):
    bh31's river that turns east to its bridge and the shoal was refused by tilecheck while the generator drew every straight 0x19."""

    @staticmethod
    def phase(rows, x, y):
        ch = lambda X, Y: rows[Y][X] if 0 <= Y < len(rows) and 0 <= X < len(rows[0]) else '~'
        return mappy.river_phase(ch, x, y)

    def test_a_run_after_the_bend_from_the_south_is_0x39(self):
        rows = ['^^^^^^', '^--=,~', '^-.^^^', '^-^^^^']
        self.assertEqual(self.phase(rows, 2, 1), 0x39)

    def test_a_run_from_the_edge_or_a_bridge_stays_0x19(self):
        self.assertEqual(self.phase(['------'], 3, 0), 0x19)
        self.assertEqual(self.phase(['^=--=^'], 2, 0), 0x19)

    def test_a_run_after_the_bend_from_the_north_stays_0x19(self):
        self.assertEqual(self.phase(['^-^^^^', '^--=,~'], 2, 1), 0x19)


class Ids(unittest.TestCase):
    def setUp(self):
        self.maps = mappy.parse(os.path.join(HERE, 'maps.txt'))
        self.ids = {}
        for l in open(os.path.join(HERE, 'map_ids.txt')):
            if l.startswith('#') or '=' not in l:
                continue
            n, _, v = l.rpartition('=')
            self.ids[n.strip()] = int(v.strip(), 0)

    def test_every_map_has_a_unique_id(self):
        names = [m['name'] for m in self.maps]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(self.ids), 'maps.txt and map_ids.txt list the same maps (run five/map.py to assign new ids)')
        self.assertEqual(len(set(self.ids.values())), len(self.ids))
        self.assertTrue(all(0 <= v <= 0xFF for v in self.ids.values()))

    def test_new_maps_come_from_the_pool(self):
        # the first twenty are the original ids; later ones must be in the pool 0xF2..0xFD
        orig = {'Five Seas', 'Iron Crossing', 'Magma Crown', 'Skyreach', 'The Citadel', 'Obelisk Duel', 'Crystal Isles', 'Obelisk Plains', 'Black Monolith',
                'Black Rampart', 'Rust Basin', 'Dune Fork', 'Cinder Flats', 'Black Wastes', 'Coral Strait', 'Trident Isles', 'Harbor Cross', 'Coral Crown',
                "The Colonel's Vault", 'Pentagon Atoll'}
        for n, v in self.ids.items():
            if n not in orig:
                self.assertIn(v, mappy.ID_POOL, n)

    def test_room_for_more_maps(self):
        cap = int(rust_const('five_map.rs', 'MAP_CAPACITY'))
        self.assertGreaterEqual(cap, 64)
        self.assertLessEqual(len(self.maps), cap)
        # ids left in the pool
        used = [v for v in self.ids.values() if v in mappy.ID_POOL]
        self.assertGreater(len(mappy.ID_POOL) - len(used), 0, 'the new-map id pool is full')

    def test_assign_ids_gives_new_maps_pool_ids(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, 'ids.txt')
            shutil.copy(os.path.join(HERE, 'map_ids.txt'), p)
            maps = [{'name': 'Brand New'}, {'name': 'Another'}]
            maps = [dict(m) for m in self.maps] + maps
            got = mappy.assign_ids(maps, p)
            self.assertEqual(got[-2:], [0xF2, 0xF3])
            self.assertTrue(maps[-1]['pack'])
            self.assertIn('Brand New = 0xF2', open(p).read())
        finally:
            shutil.rmtree(tmp)


if __name__ == '__main__':
    unittest.main()
