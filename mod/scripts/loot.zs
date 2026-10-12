// DoomRogue — weapon rarity tags, monster drops, volatile explosions

// Invisible companion that rides on a weapon pickup, glows in its rarity
// colour and applies the rolled affixes to whoever picks the weapon up.
class DR_LootTag : Actor
{
	int rarity;
	double dmg, crit, leech;
	Class<Weapon> wcls;
	int age;

	Default
	{
		+NOINTERACTION
		+NOBLOCKMAP
		+NOGRAVITY
		+DONTSPLASH
		RenderStyle "None";
	}

	static void Attach(Weapon w, int depth, int treasure)
	{
		let t = DR_LootTag(Actor.Spawn("DR_LootTag", w.pos));
		if (!t) return;
		t.tracer = w;
		t.wcls = w.GetClass();
		t.Roll(depth, treasure, w.bDropped);
	}

	void Roll(int depth, int treasure, bool dropped)
	{
		// weights: common / uncommon / rare / epic / legendary
		double shift = depth * 0.04 + treasure * 0.12;
		if (dropped) shift -= 0.25;
		double r = frandom(0, 1) + shift * frandom(0.5, 1.0);
		if (r > 1.25)      rarity = 4;
		else if (r > 1.05) rarity = 3;
		else if (r > 0.85) rarity = 2;
		else if (r > 0.55) rarity = 1;
		else               rarity = 0;

		switch (rarity)
		{
			case 1: dmg = frandom(0.08, 0.14); break;
			case 2: dmg = frandom(0.15, 0.25); crit = frandom(0.04, 0.07); break;
			case 3: dmg = frandom(0.25, 0.35); crit = frandom(0.07, 0.10); leech = frandom(0.02, 0.03); break;
			case 4: dmg = frandom(0.40, 0.55); crit = frandom(0.10, 0.14); leech = frandom(0.03, 0.05); break;
		}
	}

	override void Tick()
	{
		// do not call Super.Tick(): this actor has no physics
		if (isFrozen()) return;
		age++;
		bool taken = (tracer == null) || (Inventory(tracer) && Inventory(tracer).Owner != null);
		if (taken)
		{
			if (age > 2) GiveToNearestPlayer();
			Destroy();
			return;
		}
		SetOrigin(tracer.pos, true);
		if (rarity > 0 && (age % (6 - rarity)) == 0)
		{
			Color c = DR_Perks.RarityColor(rarity);
			A_SpawnParticle(c, SPF_FULLBRIGHT, 30, 3 + rarity,
				frandom(0, 360), frandom(-12, 12), frandom(-12, 12), frandom(0, 12),
				0, 0, frandom(0.6, 1.4) + rarity * 0.2);
		}
	}

	void GiveToNearestPlayer()
	{
		Actor best = null;
		double bd = 160;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			double d = players[i].mo.Distance2D(self);
			if (d < bd) { bd = d; best = players[i].mo; }
		}
		if (!best) return;
		let s = DR_Stats.Get(best);
		if (s && wcls) s.ApplyWeaponRoll(wcls, rarity, dmg, crit, leech);
	}
}

class DR_VolatileBlast : Actor
{
	Default
	{
		+NOGRAVITY
		+NOBLOCKMAP
		RenderStyle "Add";
		Alpha 0.9;
		Scale 1.3;
	}
	States
	{
	Spawn:
		MISL B 6 Bright NoDelay
		{
			A_StartSound("weapons/rocklx", CHAN_AUTO);
			A_Explode(96, 160, 0);   // flags 0: never hurts the player who caused it
		}
		MISL C 5 Bright;
		MISL D 4 Bright;
		Stop;
	}
}
