"""Forest monster records, transcribed from reference/lord.js:215-1395
(`monster_stats`) -- 131 flat records, no per-level grouping in the source.

lord.js record shape (each entry)::

    {name:'Small Thief', str:6, gold:56, weapon:'Small Dagger', exp:2,
     hp:9, death:'You disembowel the little thieving menace!'}

Monster records never carry a `def`/defense key anywhere in lord.js (unlike
`trainer_stats`, see masters.py) -- confirmed by grepping the whole
`monster_stats` block and by `do_attack()`/`enemy_attack()`
(reference/lord.js:6691-6997), which only ever read `op.str`/`op.hp` for
monster opponents and only read `op.def` when `pfight` (a player-vs-player
duel) is true. So `Monster` intentionally has no `defense` field.

## How lord.js groups monsters by player level

There is no explicit "level" key on any record. Instead, the forest-fight
picker (`reference/lord.js:15045-15055`) computes a flat index into
`monster_stats`:

    if (player.level === 1) {
        mnum = random(10);
    } else {
        if (random(6) !== 2) {
            mnum = ((player.level - 1) * 11) + random(10);
        } else {
            mnum = (random(player.level) * 11) + random(10);
        }
    }
    enemy = load_monster(mnum);

`random(N)` returns 0..N-1. So for level 1, mnum is uniform over indices
0-9. For level L >= 2, the *normal* case (5/6 of the time) draws uniform
over indices [(L-1)*11, (L-1)*11+9] -- and the 1/6 "wildcard" case just
redraws a level' in [0, L-1] and applies the exact same formula, so it can
never select outside the union of blocks already reachable at or below the
player's level. Net effect: each level owns a contiguous block of 11
indices, but only the first 10 of each block are ever reachable through
`mnum` -- the 11th slot in every block ((L-1)*11+10, i.e. indices 10, 21,
32, ... 120) is *dead data*: present in `monster_stats`, structurally
"belongs" to level L by position, but no reachable code path in lord.js
ever passes that index to `load_monster()`. This is very likely a
historical off-by-one in the original BBS door (block stride 11 vs. the 10
monsters actually used per level) rather than intentional reserve slots --
there's nothing distinguishing those records (no rarity/boss flag) from
their neighbours. We reproduce lord.js's actual (reachable) grouping
in `MONSTERS`, i.e. we drop the dead 11th slot per level rather than
inventing a use for it. 12 levels x 10 reachable monsters + 11 dead slots
= 131 total records, matching the source array's length exactly.

`level 1` block: monster_stats[0:10]
`level L` (2..12) block: monster_stats[(L-1)*11 : (L-1)*11+10]
"""

from collections import namedtuple

Monster = namedtuple("Monster", "name weapon strength hp gold exp death_phrase")

# Flat transcription of monster_stats, in source order, as
# (name, weapon, strength, hp, gold, exp, death_phrase).
_RAW_MONSTERS: list[tuple] = [
    ('Small Thief', 'Small Dagger', 6, 9, 56, 2, 'You disembowel the little thieving menace!'),
    ('Rude Boy', 'Cudgel', 3, 7, 7, 3, 'You quietly watch as the very Rude Boy bleeds to death.'),
    ('Old Man', 'Cane', 5, 13, 73, 4, 'You finish him off, by tripping him with his own cane.'),
    ('Large Green Rat', 'Sharp Teeth', 3, 4, 32, 1, 'A well placed step ends this small rodents life.'),
    ('Wild Boar', 'Sharp Tusks', 10, 9, 58, 5, 'You impale the boar between the eyes!'),
    ('Ugly Old Hag', 'Garlic Breath', 6, 9, 109, 4, 'You emotionally crush the hag, by calling her ugly!'),
    ('Large Mosquito', 'Blood Sucker', 2, 3, 46, 2, 'With a sharp slap, you end the Mosquitos life.'),
    ('Bran The Warrior', 'Short Sword', 12, 15, 234, 10, 'After a hardy duel, Bran lies at your feet, dead.'),
    ('Evil Wretch', 'Finger Nail', 7, 12, 76, 3, 'With a swift boot to her head, you kill her.'),
    ('Small Bear', 'Claws', 9, 7, 154, 6, 'After a swift battle, you stand holding the Bears heart!'),
    ('Small Troll', 'Uglyness', 6, 14, 87, 5, 'This battle reminds you how of how much you hate trolls.'),
    ('Green Python', 'Dripping Fangs', 13, 17, 80, 6, "You tie the mighty snake's carcass to a tree."),
    ('Gath The Barbarian', 'Huge Spiked Club', 12, 13, 134, 9, 'You knock Gath down, ignoring his constant groaning.'),
    ('Evil Wood Nymph', 'Flirtatios Behavior', 15, 10, 160, 11, 'You shudder to think of what would have happened, had you given in.'),
    ('Fedrick The Limping Baboon', 'Scary Faces', 8, 23, 97, 6, 'Fredrick will never grunt in anyones face again.'),
    ('Wild Man', 'Hands', 13, 14, 134, 8, 'Pitting your wisdom against his brawn has one this battle.'),
    ('Brorandia The Viking', 'Hugely Spiked Mace', 21, 18, 330, 20, 'You consider this a message to her people, "STAY AWAY!".'),
    ('Huge Bald Man', 'Glare From Forehead', 19, 19, 311, 16, "It wasn't even a close battle, you slaughtered him."),
    ('Senile Senior Citizen', 'Crazy Ravings', 13, 11, 270, 13, 'You may have just knocked some sense into this old man.'),
    ('Membrain Man', 'Strange Ooze', 10, 16, 190, 11, 'The monstrosity has been slain.'),
    ('Bent River Dryad', 'Pouring Waterfall', 12, 16, 150, 9, 'You cannot resist thinking the Dryad is "All wet".'),
    ('Rock Man', 'Large Stones', 8, 27, 300, 12, 'You have shattered the Rock Mans head!'),
    ('Lazy Bum', 'Unwashed Body Odor', 19, 29, 380, 18, '"This was a bum deal" You think to yourself.'),
    ('Two Headed Rotwieler', 'Twin Barking', 18, 32, 384, 17, 'You have silenced the mutt, once and for all.'),
    ('Purple Monchichi', 'Continous Whining', 14, 29, 763, 23, 'You cant help but realize you have just killed a real loser.'),
    ('Bone', 'Terrible Smoke Smell', 27, 11, 432, 16, 'Now that you have killed Bone, maybe he will get a life..'),
    ('Red Neck', 'Awfull Country Slang', 19, 16, 563, 19, 'The dismembered body causes a churning in your stomach.'),
    ('Winged Demon Of Death', 'Red Glare', 42, 23, 830, 28, 'You cut off the Demons head, to be sure of its death.'),
    ('Black Owl', 'Hooked Beak', 28, 29, 711, 26, 'A well placed blow knocks the winged creature to the ground.'),
    ('Muscled Midget', 'Low Punch', 26, 19, 870, 32, 'You laugh as the small man falls to the ground.'),
    ('Headbanger Of The West', 'Ear Shattering Noises', 23, 27, 245, 43, 'You slay the rowdy noise maker and destroy his evil machines.'),
    ('Morbid Walker', 'Endless Walking', 28, 10, 764, 9, 'Even lying dead on its back, it is still walking.'),
    ('Magical Evil Gnome', 'Spell Of Fire', 24, 25, 638, 28, "The Gnome's small body is covered in a deep red blood."),
    ('Death Dog', 'Teeth', 36, 52, 1150, 36, 'You rejoice as the dog wimpers for the very last time.'),
    ('Weak Orc', 'Spiked Club', 27, 32, 900, 25, 'A solid blow removes the Orcs head!'),
    ('Dark Elf', 'Small bow', 43, 57, 1070, 33, 'The Elf falls at your feet, dead.'),
    ('Evil Hobbit', 'Smoking Pipe', 35, 95, 1240, 46, 'The Hobbit will never bother anyone again!'),
    ('Short Goblin', 'Short Sword', 34, 45, 768, 24, 'A quick lunge renders him dead!'),
    ('Huge Black Bear', 'Razor Claws', 67, 48, 1765, 76, 'You bearly beat the Huge Bear...'),
    ('Rabid Wolf', 'Deathlock Fangs', 45, 39, 1400, 43, 'You pull the dogs lifeless body off you.'),
    ('Young Wizard', 'Weak Magic', 64, 35, 1754, 64, 'This Wizard will never cast another spell!'),
    ('Mud Man', 'Mud Balls', 56, 65, 870, 43, 'You chop up the Mud Man into sushi!'),
    ('Death Jester', 'Horrible Jokes', 34, 46, 1343, 32, 'You feel no pity for the Jester, his jokes being as bad as they were.'),
    ('Rock Man', 'Large Stones', 87, 54, 1754, 76, 'You have shattered the Rock Mans head!'),
    ('Pandion Knight', 'Orkos Broadsword', 64, 59, 3100, 98, 'You are elated in the knowledge that you both fought honorably.'),
    ('Jabba', 'Whiplashing Tail', 61, 198, 2384, 137, 'The fat thing falls down, never to squirm again.'),
    ('Manoken Sloth', 'Dripping Paws', 54, 69, 2452, 97, 'You have cut him down, spraying a neaby tree with blood.'),
    ('Trojan Warrior', 'Twin Swords', 73, 87, 3432, 154, 'You watch, as the ants claim his body.'),
    ('Misfit The Ugly', 'Strange Ideas', 75, 89, 2563, 120, 'You cut him cleanly down the middle, in a masterfull stroke.'),
    ('George Of The Jungle', 'Echoing Screams', 56, 43, 2230, 128, 'You thought the story of George was a myth, until now.'),
    ('Silent Death', 'Pale Smoke', 113, 98, 4711, 230, 'Instead of spilling blood, the creature seems filled with only air.'),
    ('Bald Medusa', 'Glare Of Stone', 78, 120, 4000, 256, 'You are lucky you didnt look at her... Man was she ugly!'),
    ('Black Alligator', 'Extra Sharp Teeth', 65, 65, 3245, 123, 'With a single stroke, you sever the creatures head right off.'),
    ('Clancy, Son Of Emporor Len', 'Spiked Bull Whip', 52, 324, 4764, 324, 'Its a pity so many new warriors get so proud.'),
    ('Black Sorcerer', 'Spell Of Lightning', 86, 25, 2838, 154, 'Thats the last spell this Sorcerer will ever cast!'),
    ('Iron Warrior', '3 Iron', 100, 253, 6542, 364, "You have bent the Iron warrior's Iron!"),
    ('Black Soul', 'Black Candle', 112, 432, 5865, 432, 'You have released the black soul.'),
    ('Gold Man', 'Rock Arm', 86, 354, 8964, 493, 'You kick the body of the Gold man to reveal some change..'),
    ('Screaming Zombie', 'Gaping Mouth Full Of Teeth', 98, 286, 5322, 354, 'The battle has rendered the zombie even more unattractive then he was.'),
    ('Satans Helper', 'Pack Of Lies', 112, 165, 7543, 453, "Apparently you have seen through the Devil's evil tricks"),
    ('Wild Stallion', 'Hoofs', 78, 245, 4643, 532, "You only wish you could have spared the animal's life."),
    ('Belar', 'Fists Of Rage', 120, 352, 9432, 565, 'Not even Belar can stop you!'),
    ('Empty Armour', 'Cutting Wind', 67, 390, 6431, 432, 'The whole battle leaves you with a strange chill.'),
    ('Raging Lion', 'Teeth And Claws', 98, 274, 3643, 365, 'You rip the jaw bone off the magnificent animal!'),
    ('Huge Stone Warrior', 'Rock Fist', 112, 232, 4942, 543, 'There is nothing left of the stone warrior, except a few pebbles.'),
    ('Magical Evil Gnome', 'Spell Of Fire', 89, 234, 6384, 321, "The Gnome's small body is covered in a deep, red blood."),
    ('Emporer Len', 'Lightning Bull Whip', 210, 432, 12043, 764, 'His last words were.. "I have failed to avenge my son."'),
    ('Night Hawk', 'Blood Red Talons', 220, 675, 10433, 686, 'Your last swing pulls the bird out of the air, landing him at your feet.'),
    ('Charging Rhinoceros', 'Rather Large Horn', 187, 454, 9853, 654, 'You finally felled the huge beast, but not without a few scratches.'),
    ('Goblin Pygmy', 'Death Squeeze', 165, 576, 13252, 754, "You laugh at the little Goblin's puny attack."),
    ('Goliath', 'Six Fingered Fist', 243, 343, 14322, 898, 'Now you know how David felt...'),
    ('Angry Liontaur', 'Arms And Teeth', 187, 495, 13259, 753, 'You have laid this mythical beast to rest.'),
    ('Fallen Angel', 'Throwing Halos', 154, 654, 12339, 483, 'You slay the Angel, then watch as it gets sucked down into the ground.'),
    ('Wicked Wombat', 'The Dark Wombats Curse', 198, 464, 13283, 786, "It's hard to believe a little wombat like that could be so much trouble."),
    ('Massive Dinosaur', 'Gaping Jaws', 200, 986, 16753, 1204, 'The earth shakes as the huge beast falls to the ground.'),
    ('Swiss Butcher', 'Meat Cleaver', 230, 453, 8363, 532, "You're glad you won...You really didn't want the haircut.."),
    ('Death Gnome', 'Touch Of Death', 270, 232, 10000, 654, 'You watch as the animals pick away at his flesh.'),
    ('Screeching Witch', 'Spell Of Ice', 300, 674, 19753, 2283, "You have silenced the witch's infernal screeching."),
    ('Rundorig', 'Poison Claws', 330, 675, 17853, 2748, 'Rundorig, once your friend, now lies dead before you.'),
    ('Wheeler', 'Annoying Laugh', 250, 786, 23433, 1980, "You rip the wheeler's wheels clean off!"),
    ('Death Knight', 'Huge Silver Sword', 287, 674, 21923, 4282, 'The Death knight finally falls, not only wounded, but dead.'),
    ('Werewolf', 'Fangs', 230, 543, 19474, 3853, "You have slaughtered the Werewolf. You didn't even need a silver bullet."),
    ('Fire Ork', 'FireBall', 267, 674, 24933, 3942, "You have put out this Fire Ork's flame!"),
    ('Wans Beast', 'Crushing Embrace', 193, 1243, 17141, 2432, 'The hairy thing has finally stopped moving.'),
    ('Lord Mathese', 'Fencing Sword', 245, 875, 24935, 2422, 'You have wiped the sneer off his face once and for all.'),
    ('King Vidion', 'Long Sword Of Death', 400, 1243, 28575, 6764, 'You feel lucky to have lived. Things could have gone sour..'),
    ('Baby Dragon', 'Dragon Smoke', 176, 2322, 25863, 3675, 'This Baby Dragon will never grow up.'),
    ('Death Gnome', 'Touch Of Death', 356, 870, 31638, 2300, 'You watch as the animals pick away at his flesh.'),
    ('Pink Elephant', 'Stomping', 434, 1232, 33844, 7843, "You have witnessed the Pink Elephant...And you aren't even drunk!"),
    ('Gwendolens Nightmare', 'Dreams', 490, 764, 35846, 8232, 'This is the first Nightmare you have put to sleep.'),
    ('Flying Cobra', 'Poison Fangs', 400, 1123, 37694, 8433, 'The creature falls to the ground with a sickening thud.'),
    ('Rentakis Pet', 'Gaping Maw', 556, 987, 37584, 9854, 'You vow to find Rentaki and tell him what you think about his new pet.'),
    ('Ernest Brown', 'Knee', 432, 2488, 34833, 9754, 'Ernest has finally learned his lesson, it seems.'),
    ('Scallian Rap', 'Way Of Hurting People', 601, 788, 22430, 6784, "Scallian's dead...Looks like you took out the trash..."),
    ('Apeman', 'Hairy Hands', 498, 1283, 38955, 7202, 'The battle is over...Nothing is left but blood and hair.'),
    ('Hemo-Glob', 'Weak Insults', 212, 1232, 27853, 4432, "The battle is over.. And you really didn't find him particularly scary."),
    ('FrankenMoose', 'Butting Head', 455, 1221, 31221, 5433, 'That Moose was a perversion of nature!'),
    ('Earth Shaker', 'Earthquake', 767, 985, 37565, 7432, 'The battle is over...And it looks like you shook him up...'),
    ('Gollums Wrath', 'Ring Of Invisibilty', 621, 2344, 42533, 13544, "Gollum's ring apparently wasn't powerful enough."),
    ('Toraks Son, Korak', 'Sword Of Lightning', 921, 1384, 46575, 13877, 'You have slain the son of a God!  You ARE great!'),
    ('Brand The Wanderer', 'Fighting Quarter Staff', 643, 2788, 38755, 13744, 'Brand will wander no more.'),
    ('The Grimest Reaper', 'White Sickle', 878, 1674, 39844, 14237, 'You have killed that which was already dead.  Odd.'),
    ('Death Dealer', 'Stare Of Paralization', 765, 1764, 47333, 13877, 'The Death Dealer has been has been dealt his last hand.'),
    ('Tiger Of The Deep Jungle', 'Eye Of The Tiger', 587, 3101, 43933, 9766, "The Tiger's cubs weep over their dead mother."),
    ('Sweet Looking Little Girl', 'Demon Strike', 989, 1232, 52322, 14534, "If it wasn't for her manners, you might have gotten along with her."),
    ('Floating Evil Eye', 'Evil Stare', 776, 2232, 43233, 13455, "You really didn't like the look of that Eye..."),
    ('Slock', 'Swamp Slime', 744, 1675, 56444, 14333, "Walking away fromm the battle, you nearly slip on the thing's slime."),
    ('Adult Gold Dragon', 'Dragon Fire', 565, 3222, 56444, 15364, 'He was strong, but you were stronger.'),
    ('Black Sorcerer', 'Spell Of Lightning', 86, 25, 2838, 187, "That's the last spell this Sorcerer will ever cast!"),
    ('Kill Joy', 'Terrible Stench', 988, 3222, 168844, 25766, "Kill Joy has fallen, and can't get up."),
    ('Gorma The Leper', 'Contagous Desease', 1132, 2766, 168774, 26333, 'It looks like the lepers fighting strategy has fallen apart..'),
    ('Shogun Warrior', 'Japenese Nortaki', 1143, 3878, 165433, 26555, 'He was tough, but not nearly tough enough.'),
    ('Apparently Weak Old Woman', '*GODS HAMMER*', 1543, 1878, 173522, 37762, "You pull back the old woman's hood, to reveal an eyeless skull."),
    ('Ables Creature', 'Bear Hug', 985, 2455, 176775, 28222, 'That was a mighty creature.  Created by a mighty man.'),
    ('White Bear Of Lore', 'Snow Of Death', 1344, 1875, 65544, 16775, "The White Bear Of Lore DOES exist you've found.  Too bad it's now dead."),
    ('Mountain', 'Landslide', 1544, 1284, 186454, 38774, 'You have knocked the mountain to the ground.  Now it IS the ground.'),
    ('Sheena The Shapechanger', 'Deadly Illusions', 1463, 1898, 165755, 26655, 'Sheena is now a quivering mass of flesh.  Her last shapechange.'),
    ('ShadowStormWarrior', 'Mystical Storm', 1655, 2767, 162445, 26181, 'The storm is over, and the sunshine greets you as the victor.'),
    ('Madman', 'Chant Of Insanity', 1265, 1764, 149564, 25665, 'Madman must have been mad to think he could beat you!'),
    ('Vegetable Creature', 'Pickled Cabbage', 111, 172, 4838, 2187, 'For once you finished off your greens...'),
    ('Cyclops Warrior', 'Fire Eye', 1744, 2899, 204000, 49299, "The dead Cyclop's one eye stares at you blankly."),
    ('Corinthian Giant', 'De-rooted Tree', 2400, 2544, 336643, 60333, 'You hope the giant has brothers, more sport for you.'),
    ('The Screaming Eunich', 'High Pitched Voice', 1488, 2877, 197888, 78884, "If it wasn't for his ugly features, you thought he looked female."),
    ('Black Warlock', 'Satanic Choruses', 1366, 2767, 168483, 58989, "You have slain Satan's only son."),
    ('Kal Torak', 'Cthrek Goru', 876, 6666, 447774, 94663, 'You have slain a God!  You are the ultimate warrior!'),
    ('The Mighty Shadow', 'Shadow Axe', 1633, 2332, 176333, 51655, 'The mighty Shadow is now only a Shadow of his former self.'),
    ('Black Unicorn', 'Shredding Horn', 1899, 1587, 336693, 41738, 'You have felled the Unicorn, not the first, not the last.'),
    ('Mutated Black Widow', 'Venom Bite', 2575, 1276, 434370, 98993, "A well placed stomp ends this Spider's life."),
    ('Humongous Black Wyre', 'Death Talons', 1166, 3453, 653834, 76000, "The Wyre's dead carcass covers the whole field!"),
    ('The Wizard Of Darkness', 'Chant Of Insanity', 1497, 1383, 224964, 39878, 'This Wizard of Darkness will never bother you again'),
    ('Great Ogre Of The North', 'Spiked Steel Mace', 1800, 2878, 524838, 112833, 'No one is going to call him The "Great" Ogre Of The North again.'),
]

assert len(_RAW_MONSTERS) == 131


def _level_slice(level: int) -> tuple[int, int]:
    if level == 1:
        return 0, 10
    start = (level - 1) * 11
    return start, start + 10


MONSTERS: dict[int, list[Monster]] = {
    level: [Monster(*row) for row in _RAW_MONSTERS[start:end]]
    for level in range(1, 13)
    for start, end in [_level_slice(level)]
}
