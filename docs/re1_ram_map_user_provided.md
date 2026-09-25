# RE1 RAM map, user-provided candidate

Provenance: pasted by user in chat on 2026-09-25. Original author unknown.
Status: Candidate. Nothing here is runtime confirmed by this project.
Scope: appears to describe original RE1 USA SLUS-00170 plus EU, FR, GER
variants, based on Region Serial and Current Frame rows. Do not apply to
SLUS-00551 Director's Cut without a live GDB test.
Address space: values look like PS1 RAM offsets. Add 0x80000000 for the
KSEG0 virtual address used by the GDB server, for example offset 0x0c51ac
means virtual 0x800c51ac. Widths follow the Note column. BE marks
big-endian, default is little-endian.

Raw table follows verbatim, reformatted only for readability. Unknown and
empty cells are preserved as given.

## Region and timing

- 0x01004c Region Serial [32-bit BE]
  - 0x55532d30=US_0 | USA=SLUS_00170
  - 0x45532d30=ES_0 | Europe=SLES_00200
  - 0x45532d30=ES_0 | France=SLES_00227
  - 0x45532d30=ES_0 | Germany=SLES_00228
- 0x010050 Region Serial [32-bit BE]
  - 0x30313730=0170 | USA=SLUS_00170
  - 0x30323030=0200 | Europe=SLES_00200
  - 0x30323237=0227 | France=SLES_00227
  - 0x30323238=0228 | Germany=SLES_00228
- 0x0ade58 Current Frame [32bits] [USA]
- 0x0ae460 Current Frame [32bits] [EU]
- 0x0aec00 Current Frame [32bits] [FR]
- 0x0aed70 Current Frame [32bits] [GER]
- 0x0bac5c Start Frame [32bits] [USA]
- 0x0bb460 Start Frame [32bits] [EU]
- 0x0bbc00 Start Frame [32bits] [FR]
- 0x0bbd70 Start Frame [32bits] [GER]
- 0x0be8e4 Timer [32bits]
- 0x0be8e8 Funny Freeze
- 0x0c866c Demo? [8-bits] 0x00=Demo 0x07=Not Demo
- 0x0c867c Event Timer (Not on pause) [16bits], restarts when timed event begins
- 0x0c8684 Time (Refresh when save menu) [32bits]
- 0x0c8688 Saves Made [8bits] (Default 1)

## Player state

- 0x0c5126 Weapon equipped 3D
- 0x0c51ac Health [8bits], 0x60 = Jill Max Original, 0x46 = Jill Max Arrange
- 0x0c51e1 Character Action [8bits]
  - 0x00 Normal, 0x01 Idle, 0x02 Walking, 0x03 Backwards and Running,
    0x05 Starting to Aim, 0x06 Shooting, 0x07 Aiming,
    0x08 Aiming Sides and Starting to Aim Up, 0x09 Shooting Up, 0x0a Aiming Up,
    0x0b Starting to Aim Down, 0x0c Shooting Down, 0x0d Aiming Down
- 0x0c51e2 Character State Time [8bits]
- 0x0c5200 Health State [8bit], Bit1 Poison, Bit4 Fine, Bit5 Poison (Yawn)
- 0x0c8667 Items in Inventory [8bits]
- 0x0c8669 Player [8bit]
  - 0x00 Chris (Before Underground and After Final Elevator)
  - 0x01 Jill (Before Underground and After Final Elevator)
  - 0x03 Rebecca (Before Underground)
  - 0x04 Chris (Underground and Laboratory)
  - 0x05 Jill (Underground and Laboratory)
  - 0x07 Rebecca (Unused?)
  - 0x09 Changing Costume
- 0x0c866d Flamethrower Ammo [8bits]
- 0x0c866e Flamethrower 2 Ammo [8bits]
- 0x0c867e Health? [16bits]
- 0x0c8689 Equiped Gun
- 0x0c8693 Game Mode [8-bit], 0x00 Standard, 0x01 Training, 0x02 Arrange, 0x03 Arrange (2x Ammo)

## Enemies

- 0x0c532c Enemy 1 Health [16bits], 0xFFFF Dead
- 0x0c5368 Enemy 1 On Ground [16bits], 0xFFFF Standing
- 0x0c542c Enemy 1 Hits to Down [16bits]

## Game flow

- 0x0c8454 GameState [8bits], 0x00 Ingame, 0x01 Not Ingame (Only if you were Ingame first)
- 0x0c8456 Saving [8bits], 0x01-2 Opening Saving, 0x03 Inside Saving
- 0x0c8457 Item Chest [8bits], 0x01-3 Opening Chest, 0x04 Inside Chest
- 0x0c8459 Cinematic/Door End [8bits], 0x01 End
- 0x0c845b Opened Inventory/Chest [8bit], Opening Door [8bits]
- 0x0cf63b Last Cutscene Played/Currently Playing [USA][EU], 0x00 Main Menu Intro through 0x19 Unlimited Launcher?
- 0x0cf9fb Last Cutscene Played/Currently Playing [FR], same list as USA/EU
- 0x0cf844 Buttons Pressed

## Location, the room identity core

- 0x0c8660 Main Location [8Bits]
  - 0x00 Mansion 1F, 0x01 Mansion 2F, 0x02 Courtyard/Underground,
    0x03 Guardhouse, 0x04 Laboratory,
    0x05 Mansion 1F Second Time, 0x06 Mansion 2F/B1 Second Time
- 0x0c8661 SubLocation [8Bits], meaning depends on Main Location.
  - Mansion 1F: 0x00 Mansion Save Room, 0x01 West Stairway 1F, 0x02 Vacant Room,
    0x03 Central Corridor, 0x04 Tea Room, 0x05 Dining Room, 0x06 Main Hall 1F,
    0x07 Art Room, 0x08 L-Passage, 0x09 Winding Passage, 0x0A Back Passage,
    0x0B East Stairway 1F, 0x0C Greenhouse, 0x0D Tiger Statue Room,
    0x0E Keeper's Room, 0x0F Bar, 0x10 Elevator Stairway, 0x11 Dressing Room,
    0x12 Wardrobe, 0x13 Bathroom, 0x14 Outside Boiler, 0x15 Trap Room,
    0x16 Living Room, 0x17 Large Gallery, 0x18 Mansion Storeroom,
    0x19 Courtyard Study, 0x1A Roofed Passage, 0x1B Store Room, 0x1C Wardrobe Closet
  - Mansion 2F: 0x00 Elevator, 0x01 West Stairway 2F, 0x02 Dining Room 2F,
    0x03 Main Hall 2F, 0x04 C-Passage, 0x05 Armor Room, 0x06 Small Library,
    0x07 East Stairway 2F, 0x08 Deer Room, 0x09 Bedroom, 0x0A Study,
    0x0B Lesson Room Entry, 0x0C Lesson Room, 0x0D Pillar Passage,
    0x0E Attic Entry, 0x0F Small Dining Room, 0x10 Attic, 0x11 Terrace Entry,
    0x12 Terrace, 0x13 Elevator 2F, 0x14 Rough Passage, 0x15 Trophy Room,
    0x16 Large Library, 0x17 Private Library, 0x18 Heliport Lookout,
    0x19 Closet, 0x1A Mansion B1 Underground Passage 1,
    0x1B Mansion B1 Underground Passage 2, 0x1C Mansion B1 Kitchen
  - Courtyard/Underground: 0x00 Garden, 0x01 Watergate, 0x02 Falls,
    0x03 Heliport, 0x04 Guardhouse Gate, 0x05 Fountain,
    0x06 Item Chamber, 0x07 Underground Entry, 0x08 Branched Passage,
    0x09 Generator Room, 0x0A Enrico Room, 0x0B Boulder Passage 1,
    0x0C Black Tiger Room, 0x0D Straight Passage, 0x0E Underground Save Room,
    0x0F Boulder Passage 2, 0x10 Laboratory Elevator
  - Guardhouse: 0x00 Guardhouse Entry, 0x01 Room 001, 0x02 Room 001 Bathroom,
    0x03 Guardhouse Save Room, 0x04 Rec Room, 0x05 Central Corridor,
    0x06 Room 002, 0x07 Room 002 Bathroom, 0x08 Beehive Passage,
    0x09 Drug Storeroom, 0x0A Room 003, 0x0B Room 003 Bathroom,
    0x0C Plant 42 Room, 0x0D Water Tank Entry, 0x0E Water Tank,
    0x0F Meeting Room, 0x10 Arms Storage, 0x11 Control Room
  - Laboratory: 0x00 Laboratory Entry, 0x01 Emergency Tunnel, 0x02 Ladder Room,
    0x03 Stairway, 0x04 Visual Data Room, 0x05 O-Room, 0x06 Small Lab,
    0x07 Operating Room / Morgue, 0x08 Private Corridor, 0x09 Private Room,
    0x0A X-Ray Room, 0x0B Cell Entry, 0x0C Elevator Entry, 0x0D Elevator,
    0x0E Lab Save Room, 0x0F Power Maze 1, 0x10 Power Maze 2, 0x11 Power Room,
    0x12 Cell, 0x13 Main Lab, 0x14 Main Lab Entry, 0x15 Elevator B3/B4
- 0x0c8662 Location Part Loaded (Camera) [8bits]
- 0x0c8663 Previous Location [8bits]

## Event flags, doors, enemies killed

- 0x0c8696 Event Flag [8bit], Jill Bit6 Sharks
- 0x0c8697 Event Flag [8bit] Jill: Bit0 ???, Bit1 Barry Acid Rounds Terrace Main Hall,
  Bit2 Master of Unlocking, Bit3 Opened Main Hall door, Bit4 Looking for Wesker Main Hall,
  Bit5 First Zombie, Bit6 Check Main Hall at Start, Bit7 Starting cinematic
- 0x0c8698 Event Flag [8bit] Jill blank, Chris Bit6 Rebecca First Encounter, Bit7 Rebecca V-Jolt?
- 0x0c8699 Event Flag [8bits] Bit0 Entered Plant 42 (Chris),
  Bit1 Rebecca can be saved and you entered the room, Bit4 Save Rebecca (In Room),
  Bit6 Saved Rebecca (goes to 0 when you talk with her), Bit7 Rebecca Dead
- 0x0c869b Event Flag [8bit] Jill Bit6 Jill Sandwich, Bit7 Crusher Room locked
- 0x0c869c Event Flag [8bit] Jill Bit1 Forest Zombie
- 0x0c869f Event Flag [8bit] Jill Bit6 L-Passage Second Dog, Bit7 L-Passage First Dog
- 0x0c86a2 Event Flag [8bits] Jill blank, Imported Bit7 Box 2 on poison hole Operating Room Lab,
  Bit2 After Killing Hunter Rebecca flees, Bit3 Killed Hunter Rebecca Library,
  Bit4 Leave Library with Hunter alive (Rebecca dies)
- 0x0c86a3 Event Flag [8bit] Jill Bit5 Meet with Richard, Bit7 Keeper Bedroom Zombie,
  Chris Bit0 Entered Library Rebecca, Imported Bit0 Box 1 on poison hole Operating Room Lab,
  Bit2 Richard dead (Chris), Bit3 player fails to save Richard, Bit4 Jill can trigger save Richard with Serum,
  Bit6 Richard dead (Jill)
- 0x0c86a9 Event Flag [8bit] Jill Bit3 Zombie cinematic by being a Coward
- 0x0c86aa Event Flag [8bit] Jill Bit2 Barry following in Dining Room, Bit3 Entered Tea Room
- 0x0c86ab Event Flag [8bit-BE] Jill Bit2 Piano Door Open, Bit4 Lost courage already?,
  Bit5 Hope this is not Chris Blood, Bit6 Barry kills first zombie, Bit7 First cinematic Dining Room
- 0x0c86ae Event Flag [8bit] Jill Bit3 ???, Bit5 West Stairway 1F First Dog,
  Bit6 West Stairway 1F Second Dog, Bit7 West Stairway 1F Third Dog
- 0x0c86b4 Desks [8bit] Bit0 Dressing Room, Bit1 Vacant Room
- 0x0c86b5 Doors [8bit] Bit1 C Passage East Stairway 2F, Bit2 Small Library East Stairway 2F,
  Bit3 Back Passage East Stairway 1F, Bit5 Central Corridor Tea Room
- 0x0c86b6 Doors [8bit] Bit1 C Passage Armor Room, Bit2 C Passage Pillar Passage,
  Bit4 Central Corridor Keeper Bedroom, Bit5 West Stairway 1F Vacant Room, Bit6 Art Room L Passage
- 0x0c86b7 Doors [8bit] Bit1 Tea Room Bar, Bit2 Main Hall Dressing Room, Bit6-7 Trap Room
- Enemy Killed bytes 0x0c86bc through 0x0c86d7, per-room zombie, Cerberus, crow,
  dog, turbo zombie, Forest Zombie, Hunter bits as given in chat. Not repeated here
  in full to keep this file short. See chat log for the full bit list. These do not
  block clearing per AGENTS.md unless game data proves otherwise.

## Item Collected bitfields

- 0x0c86dc Bit0 Star Crest, Bit4 Armor Key
- 0x0c86dd Bit1 Mansion Save Room Ink Ribbon (Jill), Bit4 L Passage Clips
- 0x0c86de Bit1 Acid Rounds from Barry
- 0x0c86df Bit0 Music Notes, Bit1 Bazooka, Bit2 Keeper Room Shells, Bit3 Keeper Diary,
  Bit5 Dressing Room Shells, Bit6 Broken Shotgun in Shotgun Room, Bit7 Shotgun
- 0x0c86e1 Bit5 Vacant Room Clips, Bit6 Vacant Room Shells, Bit7 Broken Shotgun
- 0x0c86e2 Bit6 Tea Room Clips
- 0x0c86e3 Bit0 Art Room Ink Ribbon
- 0x0c86ea Bit0 Winding Passage Green Herb, Bit1 East Stairway 1F Green Herb
- 0x0c86eb Bit6 Bathroom Clips, Bit7 Dressing Room Clips
- 0x0c86ed Bit5 Keeper Bedroom Clips, Bit6 Map on Art Room
- 0x0c86ee Bit0-1 Wardrobe Green Herbs
- 0x0c86f2 Bit0 Colt Python, Bit3 ??? Almost since the start
- 0x0c86f5 Bit3 Wardrobe Ink Ribbon
- 0x0c86f9 Bit0 Small Library Botany Book

## Maps, files, unlocks

- 0x0c8702 Bit4 Statue Pushed Dining Room, Bit6 First Time you enter East Stairway 1F
- 0x0c870c Inventory Unlocks [8bits] Bit0 Radio, Bit1 Infinite Rocket Launcher,
  Bit3 Lockpick, Bit5 Infinite Colt Python
- 0x0c870d Events [8bit] Bit6 Bathroom Zombie Triggered, Bit7 Alternate Jill Costume
- 0x0c870e Static Events [8bit] Bit0 Original Jill Costume
- Map Visited 0x0c8710 Bit0 Issolated Passage, Bit1 Bar Secret Passage,
  Bit2 Art Room Secret Room, Bit7 Mansion Storeroom, Bits 3-6 empty as given
- Map Visited 0x0c8711 Bit0 Large Gallery, Bit1 Living Room, Bit2 Trap Room,
  Bit3 Outside Boiler, Bit4 Bathroom, Bit5 Wardrobe, Bit6 Dressing Room, Bit7 Elevator Stairway
- Map Visited 0x0c8712 Bit0 Bar, Bit1 Keeper Bedroom, Bit2 Tiger Statue Room,
  Bit3 Greenhouse, Bit4 East Stairway, Bit5 Back Passage, Bit6 Winding Passage, Bit7 L Passage
- Map Visited 0x0c8713 Bit0 Art Room, Bit1 Main Hall, Bit2 Dining Room, Bit3 Tea Room,
  Bit4 Central Corridor, Bit5 Vacant Room, Bit6 West Stairway 1F, Bit7 Mansion Save Room
- Map Visited 0x0c8715 Bit5 Terrace, Bit6 Terrace Entry
- Map Visited 0x0c8716 Bit4 Lesson Room Entry, Bit5 Study, Bit6 Bedroom, Bit7 Deer Room
- Map Visited 0x0c8717 Bit0 East Stairway 1F, Bit1 ???, Bit3 C Passage, Bit4 Main Hall 2F,
  Bit5 Dinning Room 2F, Bit6 West Stairway 2F, Bit7 empty as given
- Maps 0x0c871c Bit0 Courtyard B1, Bit1 Courtyard 1F, Bit2 Mansion 2F, Bit3 Mansion 1F
- Files 0x0c8721 File 2 Bit6 Botany Book, Bit7 Pass Code03
- Files 0x0c8722 File 2 Bit0 Pass Code02, Bit1 Pass Code01, Bit2 Barry Picture,
  Bit3 V-Jolt Report, Bit4 Researcher Letter, Bit5 Security System,
  File 1 Bit6 Scrapbook, Bit7 Fax
- Files 0x0c8723 File 1 Bit0 Plant42 Report, Bit1 Pass Number, Bit2 Orders,
  Bit3 Keeper Diary, Bit5 Researcher Will

## Chest and inventory slots

- 0x0c8724 Chest Item Slots [768bits] with 0x01 Knife through 0x4d Com. Radio (Unused)
  as given in chat. Values are item IDs. Quantity and position bytes follow at
  0x0c8725, 0x0c8726, 0x0c8728, 0x0c872a, 0x0c872c, 0x0c872e.
- 0x0c8784 through 0x0c878f Inventory Slots 1-6 plus quantity bytes interleaved.
- 0x0c8790 through 0x0c879b Jill slots 7-8 and Rebecca slots 1-6 plus quantities.
