# RE3 owned-disc identity

## RE3-ID-001: repeatable static identity for the supplied disc

Status: Candidate for Resident Evil 3: Nemesis, PlayStation, USA target,
NTSC-U marker, serial SLUS-00923. These are static observations of the supplied
disc, not runtime confirmation. Hard is the human-selected difficulty; static
identity does not establish that difficulty in a running game.

The human supplied `Resident Evil 3 - Nemesis.cue` and
`Resident Evil 3 - Nemesis.bin` under `~/Games/DuckStation` on 2026-11-05.
This work independently read those files. It did not use the parent's extracted
executable or metadata as input. No emulator was booted or tested, so no
DuckStation runtime version applies. No user settings, saves or histories were
read or modified.

### Exact input and boot identity

The supplied CUE declares one BINARY file, track 01 MODE2/2352, index 01
00:00:00. The hashes below cover exact file bytes, including CUE line endings.
They identify this supplied image; no external verified-dump checksum was used.
The executable hash identifies the revision for subsequent static work. A
marketing revision label, mastering revision and runtime support remain
unestablished.

| Input | Bytes | SHA256 |
| --- | ---: | --- |
| CUE | 91 | `ffb65655915a792780922cbf5a925235d223017cbf317c1551e9748d37451b2f` |
| BIN, complete raw image | 722165136 | `d6c828dc92d50b28fd58329dbe607d4d22eeaeb1d9a46be54ac81b130fc2c7a6` |
| ISO `SYSTEM.CNF;1` | 70 | `e65213370cee375b5a062be2a046e7784f4ef96be07c1e6a6263ca5fab909c4d` |
| ISO `SLUS_009.23;1`, complete PS-X executable | 868352 | `2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29` |

`SYSTEM.CNF` selects `BOOT = cdrom:\SLUS_009.23;1`. Serial SLUS-00923 is
normalized from that filename. The PS-X marker at executable file offset
`0x4C` selects NTSC-U under DuckStation's region rule. The USA title is the
supplied target, not a new runtime observation. Region interpretation follows
[DuckStation `BIOS::GetPSExeDiscRegion`, lines 317-329](https://github.com/stenzek/duckstation/blob/dd4a0eb779296a525f8b10b6d9a45911ad6d088f/src/core/bios.cpp#L317-L329).

### Raw image and ISO checks

There are 307043 complete raw sectors of 2352 bytes, with no trailing partial
sector. Every sector has the expected sync pattern, Mode 2 byte and matching
four-byte XA subheader copies. The submode Form 2 bit counts 278579 Form 1
sectors and 28464 Form 2 sectors. This checks structure; EDC/ECC, subchannel
data, audio/video decoding and fidelity to an original pressing were not checked.
The scan rejects malformed structure rather than repairing it.

The ISO primary volume is at logical LBA 16. System ID is `PLAYSTATION`, volume
ID is `SLUS_00923`, logical blocks are 2048 bytes, and the declared volume is
307043 blocks. Root directory LBA is 22, length 2048 bytes. ISO little/big-endian
copies agree for the volume, block size and inspected root records.
`SLUS_009.23;1` begins at LBA 288380 and `SYSTEM.CNF;1` at LBA 288804.
Both files and the inspected ISO metadata use Form 1 sectors.

Here LBA is a logical disc block number with origin at CUE index 01. For this
exact zero-offset single track, logical data begins at raw BIN file offset
`LBA * 2352 + 24`. These offsets are not PS1 addresses. XA submode is one byte
at raw sector offset 18, mask `0x20`, with its duplicate at offset 22.
Mode is one byte at offset 15, full mask `0xFF`. Byte fields have no endian
conversion. Raw-sector terminology follows
[DuckStation `CDImage`, lines 22-55 and 71-77](https://github.com/stenzek/duckstation/blob/dd4a0eb779296a525f8b10b6d9a45911ad6d088f/src/util/cd_image.h#L22-L77).
The Form 2 mask follows
[DuckStation `CDROM::XASubHeader`, lines 231-247](https://github.com/stenzek/duckstation/blob/dd4a0eb779296a525f8b10b6d9a45911ad6d088f/src/core/cdrom.cpp#L231-L247).

The separate existing directory walker lists 1354 files and zero standalone
filenames ending in `.RDT`. This does not prove room data is absent or establish
an archive format. No room parser or runtime profile is introduced here.

### PS-X header and address spaces

The magic is PS-X EXE and the header occupies `0x800` file bytes. Every field
below is an unsigned 32-bit little-endian header value with full mask
`0xFFFFFFFF`. The first column contains executable file offsets, not addresses.
Field meanings follow
[DuckStation `BIOS::PSEXEHeader`, lines 60-77](https://github.com/stenzek/duckstation/blob/dd4a0eb779296a525f8b10b6d9a45911ad6d088f/src/core/bios.h#L60-L77),
pinned to commit `dd4a0eb779296a525f8b10b6d9a45911ad6d088f`. This is a
format source, not an emulator version tested with this disc.

| File offset | Field and address space | Observed value |
| --- | --- | --- |
| `0x10` | Initial PC, PS1 virtual address | `0x80011B80` |
| `0x14` | Initial GP header value, PS1 virtual address field | `0x00000000` |
| `0x18` | Payload load address, PS1 virtual | `0x80010000` |
| `0x1C` | Payload byte count, excluding header | `0x000D3800`, 866304 |
| `0x20`, `0x24` | Unknown fields, no address meaning assigned | both zero |
| `0x28` | Memory-fill address header value, PS1 virtual field | zero |
| `0x2C` | Memory-fill byte count | zero |
| `0x30` | Initial stack base, PS1 virtual | `0x801FFFF0` |
| `0x34` | Initial stack offset in bytes | zero |

The payload occupies executable file interval `[0x800, 0xD4000)` and declares
PS1 virtual interval `[0x80010000, 0x800E3800)`. Its size exactly matches the
file length minus the header. The initial PC is inside that interval.
For a virtual address inside that payload, use executable file offset
`0x800 + virtual_address - 0x80010000`; initial PC maps to `0x2380`.
This conversion does not establish loaded RAM contents, a host-process address
or any game-state field. No state address is inferred from another game.

### Reproduction, helper contract and evidence

Run from the repository root with the authorized interpreter:

```sh
/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-improvement-_b504zzf/clean-venv/bin/python \
  tools/re3_disc_identity.py \
  '/Users/adamekka/Games/DuckStation/Resident Evil 3 - Nemesis.cue'
```

[The helper](../../../tools/re3_disc_identity.py) exports `inspect_disc(cue)`
and prints schema-version-1 JSON with hashes, byte counts, disc LBAs and
explicitly named PS1 virtual header values. It reuses `_read_dir` and
`_sector_data` from the existing ISO reader without changing RE1/RE2 code.
It supports the supplied single-track layout and root serial-named boot file
at ISO version 1. Other layouts, missing or ambiguous boot entries, inconsistent
sizes, unknown region markers and malformed inspected data fail explicitly.
CLI failures return 1, write a diagnostic to stderr and emit no partial JSON.
It computes identity without accepting unknown media as a supported profile.
Future generation must compare the required executable fingerprint explicitly.

Private evidence is under
`/var/folders/9d/q5n746z953bcs654g_1sqcy80000gn/T/re-map-re3-identity-20261105-zdg0lyun/`.
`initial-static.json`, `files.json` and `boot.exe` retain the independent first
inspection, full file listing and private executable. `identity-a.json` and
`identity-b.json` are byte-identical repeat helper outputs, each with SHA256
`7d275f1bb4e290c4d05d5df0f58da7d18ef2e7ada1c7c4d129ed902a267d7405`.
`shasum.txt` records independent macOS `shasum -a 256` agreement for the CUE,
BIN and private executable; `verification.json` records these comparisons.
The initial inspection JSON has SHA256
`c1cbcae6ba3852c5bf59f52d31441c0de02d3fa7558232288f88282b8708bf2a`;
the full listing JSON has SHA256
`0eaeedd8cc7b6941b6288538ccfdef0d063094de49f491423bc5b591fcd95a1c`.
These temporary artifacts may expire; the owned-media command reproduces the
findings. Executable bytes and disc content remain outside Git.

[Synthetic regressions](../../../tests/test_re3_disc_identity.py) exercise
fingerprinting, mixed XA forms, strict CUE origin/layout, corruption, ISO bounds,
version/duplicate rejection, required boot selection, header consistency and
atomic CLI output. They contain no game data and are not gameplay evidence.

Verification used Python 3.14.10 and the assigned private interpreter. Run
`python -m pytest -q tests/test_re3_disc_identity.py tests/test_re1_profile.py
tests/test_re2_profile.py tests/test_re2_metadata.py` for the focused suite.
All 805 tests pass, including 43 new static-inspector cases. Scoped Ruff
E4/E7/E9/F/I checks, excluding the repository's test import-path pattern E402,
Ruff formatting and whitespace checks pass. The implementation agent's scoped
review checked byte counts and hashes against the owned media, address-space
labels, strict failures, shared-reader reuse and absence of game bytes from the
diff. No existing runtime profile, tracker, UI, persistence or source reader was
changed. This test scope does not establish playthrough readiness.

No external model review was run, as this workstream prohibits delegation and
the parent's configured external reviewers were unavailable. No endorsement
or runtime validation is claimed. The parent owns integration and final review.

Contributions:

- 2026-11-05; human user; supplied the owned media, requested parallel RE3
  investigation and selected Hard difficulty, as relayed in the assigned task.
- 2026-11-05; implementation agent, exact executing model `gpt-6.1-sol`;
  independently inspected the owned CUE/BIN and executable, implemented the
  metadata-only helper and synthetic tests, and wrote this topic record. Model
  attribution was verified from the matching local session's latest
  `turn_context.payload.model`, with `session_meta.payload.id` equal to
  `CODEX_THREAD_ID`. The parent supplied initial observations separately; this
  independent inspection agrees with its reported boot/hash/header values.
