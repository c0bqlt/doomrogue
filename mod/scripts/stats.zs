// DoomRogue — per-run player state, carried between floors as an inventory item

class DR_Stats : Inventory
{
	int xp;
	int lvl;
	int pendingPerks;
	int stacks[DR_Perks.NUM_PERKS];
	int perksTaken;

	bool offerActive;
	int offer[3];

	int kills;
	int floorsCleared;
	double leechAcc;

	// per-weapon affixes (keyed by weapon class)
	Array<Class<Weapon> > wClass;
	Array<int> wRarity;
	Array<double> wDmg;
	Array<double> wCrit;
	Array<double> wLeech;
	int bestRarity;
	String bestWeapon;

	// feedback for the HUD
	String toast;
	int toastTic;
	int critTic;
	int levelUpTic;

	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	override void BeginPlay()
	{
		Super.BeginPlay();
		lvl = 1;
	}

	static clearscope int XPForLevel(int l)
	{
		int n = l - 1;
		return 200 + 150 * n + 20 * n * n;
	}

	static DR_Stats Get(Actor mo)
	{
		if (!mo) return null;
		let s = DR_Stats(mo.FindInventory("DR_Stats"));
		if (!s)
		{
			mo.GiveInventory("DR_Stats", 1);
			s = DR_Stats(mo.FindInventory("DR_Stats"));
		}
		return s;
	}

	void ShowToast(String msg)
	{
		toast = msg;
		toastTic = Level.totaltime;
		Console.PrintfEx(PRINT_LOG, "%s", msg);
	}

	// ------------------------------------------------------------------ XP

	void AddXP(int amount)
	{
		xp += amount;
		while (xp >= XPForLevel(lvl))
		{
			xp -= XPForLevel(lvl);
			lvl++;
			pendingPerks++;
			levelUpTic = Level.totaltime;
			if (Owner) Owner.A_StartSound("misc/p_pkup", CHAN_AUTO, CHANF_UI, 1.0, ATTN_NONE);
		}
	}

	// ------------------------------------------------------------------ perks

	void RollOffer()
	{
		Array<int> pool;
		for (int i = 0; i < DR_Perks.NUM_PERKS; i++)
		{
			if (stacks[i] < DR_Perks.PerkMax(i)) pool.Push(i);
		}
		for (int k = 0; k < 3; k++)
		{
			if (pool.Size() == 0) { offer[k] = -1; continue; }
			int pick = random(0, pool.Size() - 1);
			offer[k] = pool[pick];
			pool.Delete(pick);
		}
		offerActive = (offer[0] >= 0);
		if (!offerActive) pendingPerks = 0;   // everything maxed
	}

	void ChoosePerk(int idx)
	{
		if (!offerActive || idx < 0 || idx > 2) return;
		int p = offer[idx];
		if (p < 0) return;
		stacks[p]++;
		perksTaken++;
		pendingPerks--;
		offerActive = false;
		ApplyPerkNow(p);
		ShowToast(String.Format("\cfPerk gained:\c- %s (%d/%d)", DR_Perks.PerkName(p), stacks[p], DR_Perks.PerkMax(p)));
	}

	void ApplyPerkNow(int p)
	{
		let pmo = PlayerPawn(Owner);
		if (!pmo) return;
		if (p == DR_Perks.P_VITALITY)
		{
			pmo.BonusHealth += 25;
			pmo.GiveBody(25);
		}
		else if (p == DR_Perks.P_FLEETFOOT)
		{
			pmo.Speed = 1.0 + 0.08 * stacks[p];
		}
	}

	// called by the main handler when a fresh floor starts
	void OnNewFloor(int floornum)
	{
		if (!Owner) return;
		if (floornum > 1) floorsCleared = floornum - 1;
		int arm = stacks[DR_Perks.P_ARMORER];
		if (arm > 0 && floornum > 1)
		{
			for (int i = 0; i < 25 * arm; i++) Owner.GiveInventory("ArmorBonus", 1);
		}
		int qm = stacks[DR_Perks.P_QUARTERMASTER];
		if (qm > 0 && floornum > 1)
		{
			for (let it = Owner.Inv; it != null; it = it.Inv)
			{
				let am = Ammo(it);
				if (am) am.Amount = min(am.MaxAmount, am.Amount + int(am.MaxAmount * 0.2 * qm));
			}
		}
		// keep speed in sync (e.g. after loading)
		if (stacks[DR_Perks.P_FLEETFOOT] > 0) Owner.Speed = 1.0 + 0.08 * stacks[DR_Perks.P_FLEETFOOT];
	}

	// ------------------------------------------------------------------ weapons

	int WeaponIndex(Class<Weapon> c) const
	{
		for (int i = 0; i < wClass.Size(); i++) if (wClass[i] == c) return i;
		return -1;
	}

	void ApplyWeaponRoll(Class<Weapon> c, int rarity, double dmg, double crit, double leech)
	{
		int i = WeaponIndex(c);
		String wname = GetDefaultByType(c).GetTag();
		if (i < 0)
		{
			wClass.Push(c); wRarity.Push(rarity); wDmg.Push(dmg); wCrit.Push(crit); wLeech.Push(leech);
		}
		else
		{
			// duplicates: keep the best of each stat, plus a small bump
			wRarity[i] = max(wRarity[i], rarity);
			wDmg[i] = max(wDmg[i], dmg) + 0.03;
			wCrit[i] = max(wCrit[i], crit);
			wLeech[i] = max(wLeech[i], leech);
			dmg = wDmg[i]; crit = wCrit[i]; leech = wLeech[i]; rarity = wRarity[i];
		}
		if (rarity >= bestRarity)
		{
			bestRarity = rarity;
			bestWeapon = DR_Perks.RarityName(rarity) .. " " .. wname;
		}
		String msg = DR_Perks.RarityColorCode(rarity) .. DR_Perks.RarityName(rarity) .. " " .. wname .. "\c-";
		if (dmg > 0) msg = msg .. String.Format("  +%d%% dmg", int(dmg * 100 + 0.5));
		if (crit > 0) msg = msg .. String.Format("  +%d%% crit", int(crit * 100 + 0.5));
		if (leech > 0) msg = msg .. String.Format("  %d%% leech", int(leech * 100 + 0.5));
		ShowToast(msg);
	}

	clearscope int CurWeaponIndex() const
	{
		if (!Owner || !Owner.player || !Owner.player.ReadyWeapon) return -1;
		let c = Owner.player.ReadyWeapon.GetClass();
		for (int i = 0; i < wClass.Size(); i++) if (wClass[i] == c) return i;
		return -1;
	}

	// ------------------------------------------------------------------ damage

	override void ModifyDamage(int damage, Name damageType, out int newdamage, bool passive, Actor inflictor, Actor source, int flags)
	{
		if (damage <= 0) return;
		if (passive)
		{
			double red = 0.12 * stacks[DR_Perks.P_THICKSKIN];
			newdamage = max(1, int(damage * (1.0 - red) + 0.5));
			return;
		}
		double mult = 1.0 + 0.15 * stacks[DR_Perks.P_BRUTE];
		double crit = 0.08 * stacks[DR_Perks.P_CRIT];
		int wi = CurWeaponIndex();
		if (wi >= 0)
		{
			mult += wDmg[wi];
			crit += wCrit[wi];
		}
		if (crit > 0 && frandom(0, 1) < crit)
		{
			mult *= 2.5;
			critTic = Level.totaltime;
		}
		newdamage = max(1, int(damage * mult + 0.5));
	}

	// called from the handler when the owner damages a monster
	void OnDealtDamage(int dmg)
	{
		double leech = 0.04 * stacks[DR_Perks.P_VAMPIRE];
		int wi = CurWeaponIndex();
		if (wi >= 0) leech += wLeech[wi];
		if (leech <= 0 || !Owner) return;
		leechAcc += min(dmg, 200) * leech;
		if (leechAcc >= 1)
		{
			int h = int(leechAcc);
			leechAcc -= h;
			Owner.GiveBody(h);
		}
	}

	void OnKill(Actor victim)
	{
		kills++;
		int adr = stacks[DR_Perks.P_ADRENALINE];
		if (adr > 0 && Owner) Owner.GiveBody(3 * adr);
	}

	// ------------------------------------------------------------------ tick

	override void DoEffect()
	{
		Super.DoEffect();
		if (!Owner || Owner.health <= 0) return;

		let shard = Owner.FindInventory("DR_PerkShard");
		if (shard && shard.Amount > 0)
		{
			pendingPerks += shard.Amount;
			shard.Amount = 0;
			shard.Destroy();
		}
		if (pendingPerks > 0 && !offerActive) RollOffer();

		int rg = stacks[DR_Perks.P_REGEN];
		if (rg > 0)
		{
			int period = 60 - 15 * rg;   // 45 / 30 / 15 tics
			int cap = int(Owner.GetMaxHealth(true) * 0.6);
			if (Level.maptime % period == 0 && Owner.health < cap) Owner.GiveBody(1, cap);
		}
	}
}

// Rare drop: grants an extra perk choice.
class DR_PerkShard : Inventory
{
	Default
	{
		Inventory.PickupMessage "Perk shard! Choose an extra perk.";
		Inventory.PickupSound "misc/p_pkup";
		+FLOATBOB
		+NOGRAVITY
		+INVENTORY.UNDROPPABLE
		Inventory.MaxAmount 99;
		RenderStyle "Add";
		Scale 0.7;
	}
	States
	{
	Spawn:
		SOUL ABCDCB 6 Bright;
		Loop;
	}
}
