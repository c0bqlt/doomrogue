// DoomRogue — perk definitions

class DR_Perks play
{
	enum EPerk
	{
		P_BRUTE,
		P_THICKSKIN,
		P_VAMPIRE,
		P_VITALITY,
		P_FLEETFOOT,
		P_REGEN,
		P_CRIT,
		P_ADRENALINE,
		P_VOLATILE,
		P_SCAVENGER,
		P_TREASURE,
		P_ARMORER,
		P_QUARTERMASTER,
		NUM_PERKS
	}

	static clearscope String PerkName(int p)
	{
		switch (p)
		{
			case P_BRUTE:         return "Brute Force";
			case P_THICKSKIN:     return "Thick Skin";
			case P_VAMPIRE:       return "Vampirism";
			case P_VITALITY:      return "Vitality";
			case P_FLEETFOOT:     return "Fleet Foot";
			case P_REGEN:         return "Regeneration";
			case P_CRIT:          return "Keen Eye";
			case P_ADRENALINE:    return "Adrenaline";
			case P_VOLATILE:      return "Volatile Corpses";
			case P_SCAVENGER:     return "Scavenger";
			case P_TREASURE:      return "Treasure Hunter";
			case P_ARMORER:       return "Armorer";
			case P_QUARTERMASTER: return "Quartermaster";
		}
		return "?";
	}

	static clearscope String PerkShort(int p)
	{
		switch (p)
		{
			case P_BRUTE:         return "BRU";
			case P_THICKSKIN:     return "SKN";
			case P_VAMPIRE:       return "VMP";
			case P_VITALITY:      return "VIT";
			case P_FLEETFOOT:     return "SPD";
			case P_REGEN:         return "REG";
			case P_CRIT:          return "CRT";
			case P_ADRENALINE:    return "ADR";
			case P_VOLATILE:      return "VOL";
			case P_SCAVENGER:     return "SCV";
			case P_TREASURE:      return "TRS";
			case P_ARMORER:       return "ARM";
			case P_QUARTERMASTER: return "QTM";
		}
		return "?";
	}

	static clearscope String PerkDesc(int p)
	{
		switch (p)
		{
			case P_BRUTE:         return "+15% damage with\nall weapons.";
			case P_THICKSKIN:     return "Take 12% less\ndamage.";
			case P_VAMPIRE:       return "Heal for 4% of\nall damage dealt.";
			case P_VITALITY:      return "+25 max health.\nHeals 25 now.";
			case P_FLEETFOOT:     return "Move 8% faster.";
			case P_REGEN:         return "Slowly regenerate\nhealth up to 60%.";
			case P_CRIT:          return "+8% chance to crit\nfor 2.5x damage.";
			case P_ADRENALINE:    return "Every kill heals\n3 health.";
			case P_VOLATILE:      return "Kills have a 12%\nchance to explode.";
			case P_SCAVENGER:     return "Monsters drop loot\nmore often.";
			case P_TREASURE:      return "Weapons roll\nhigher rarities.";
			case P_ARMORER:       return "+25 armor at the\nstart of each floor.";
			case P_QUARTERMASTER: return "Restock 20% of all\nammo each floor.";
		}
		return "";
	}

	static clearscope int PerkMax(int p)
	{
		switch (p)
		{
			case P_BRUTE:         return 5;
			case P_THICKSKIN:     return 4;
			case P_VAMPIRE:       return 3;
			case P_VITALITY:      return 4;
			case P_FLEETFOOT:     return 3;
			case P_REGEN:         return 3;
			case P_CRIT:          return 4;
			case P_ADRENALINE:    return 3;
			case P_VOLATILE:      return 3;
			case P_SCAVENGER:     return 3;
			case P_TREASURE:      return 3;
			case P_ARMORER:       return 3;
			case P_QUARTERMASTER: return 2;
		}
		return 1;
	}

	// --- rarity ----------------------------------------------------------

	static clearscope String RarityName(int r)
	{
		switch (r)
		{
			case 1: return "Uncommon";
			case 2: return "Rare";
			case 3: return "Epic";
			case 4: return "Legendary";
		}
		return "Common";
	}

	static clearscope String RarityColorCode(int r)
	{
		switch (r)
		{
			case 1: return "\cd";   // green
			case 2: return "\ch";   // blue
			case 3: return "\ct";   // purple
			case 4: return "\cf";   // gold
		}
		return "\cj";               // white
	}

	static clearscope Color RarityColor(int r)
	{
		switch (r)
		{
			case 1: return Color(255, 48, 255, 64);
			case 2: return Color(255, 48, 128, 255);
			case 3: return Color(255, 192, 64, 255);
			case 4: return Color(255, 255, 192, 32);
		}
		return Color(255, 200, 200, 200);
	}
}
