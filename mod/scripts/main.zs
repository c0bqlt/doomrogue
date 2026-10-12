// DoomRogue — run state and world rules

class DR_Main : StaticEventHandler
{
	// run info (from the DRINFO lump written by the generator)
	int totalFloors;
	int seed;

	// permadeath / summary
	bool runOver;
	bool victory;
	int sumFloor, sumLevel, sumKills, sumPerks, sumTime;
	String sumBest, sumPerkList;
	int runOverTic;

	// current floor
	String floorTitle;
	int floorStartTic;
	Array<Sector> victorySectors;
	int sealedMsgTic;

	ui int uiDelay;

	// ------------------------------------------------------------------ setup

	override void OnRegister()
	{
		ReadRunInfo();
	}

	void ReadRunInfo()
	{
		totalFloors = 12;
		int lump = Wads.FindLump("DRINFO");
		if (lump < 0) return;
		String txt = Wads.ReadLump(lump);
		Array<String> lines;
		txt.Split(lines, "\n");
		foreach (l : lines)
		{
			Array<String> kv;
			l.Split(kv, "=");
			if (kv.Size() != 2) continue;
			if (kv[0] == "floors") totalFloors = kv[1].ToInt();
			else if (kv[0] == "seed") seed = kv[1].ToInt();
		}
	}

	override void NewGame()
	{
		runOver = false;
		victory = false;
	}

	override void WorldLoaded(WorldEvent e)
	{
		floorTitle = Level.LevelName;
		floorStartTic = Level.totaltime;

		victorySectors.Clear();
		let it = Level.CreateSectorTagIterator(999);
		int idx;
		while ((idx = it.Next()) >= 0) victorySectors.Push(Level.Sectors[idx]);

		if (e.IsSaveGame || e.IsReopen) return;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			let s = DR_Stats.Get(players[i].mo);
			if (s) s.OnNewFloor(Level.levelnum);
		}
	}

	override void PlayerEntered(PlayerEvent e)
	{
		if (players[e.PlayerNumber].mo) DR_Stats.Get(players[e.PlayerNumber].mo);
	}

	// ------------------------------------------------------------------ monsters

	override void WorldThingSpawned(WorldEvent e)
	{
		let t = e.Thing;
		if (!t) return;
		if (t.bIsMonster)
		{
			double mult = 1.0 + 0.07 * max(0, Level.levelnum - 1);
			t.Health = int(t.Health * mult);
			t.StartHealth = t.Health;
		}
		else if (t is "Weapon" && Inventory(t).Owner == null)
		{
			int treasure = 0;
			let pmo = players[consoleplayer].mo;
			if (pmo)
			{
				let s = DR_Stats(pmo.FindInventory("DR_Stats"));
				if (s) treasure = s.stacks[DR_Perks.P_TREASURE];
			}
			DR_LootTag.Attach(Weapon(t), Level.levelnum, treasure);
		}
	}

	override void WorldThingDamaged(WorldEvent e)
	{
		if (!e.Thing || !e.Thing.bIsMonster || !e.DamageSource || !e.DamageSource.player) return;
		if (e.Thing == e.DamageSource) return;
		let s = DR_Stats(e.DamageSource.FindInventory("DR_Stats"));
		if (s) s.OnDealtDamage(e.Damage);
	}

	override void WorldThingDied(WorldEvent e)
	{
		let t = e.Thing;
		if (!t || !t.bIsMonster) return;
		int xp = max(1, t.SpawnHealth() / 2);
		Actor killer = null;
		for (int i = 0; i < MAXPLAYERS; i++)
		{
			if (!playeringame[i] || !players[i].mo) continue;
			let st = DR_Stats.Get(players[i].mo);
			if (!st) continue;
			st.AddXP(xp);
			st.OnKill(t);
			killer = players[i].mo;
		}
		if (!killer) return;
		let s = DR_Stats(killer.FindInventory("DR_Stats"));
		if (!s) return;

		// volatile corpses
		int vol = s.stacks[DR_Perks.P_VOLATILE];
		if (vol > 0 && frandom(0, 1) < 0.12 * vol)
		{
			let b = Actor.Spawn("DR_VolatileBlast", t.pos + (0, 0, t.height * 0.5));
			if (b) b.target = killer;
		}

		// loot drops
		double chance = 0.16 + 0.10 * s.stacks[DR_Perks.P_SCAVENGER] + min(0.15, t.SpawnHealth() / 4000.0);
		if (frandom(0, 1) < chance) DropLoot(t, killer);
		if (frandom(0, 1) < 0.012 + 0.002 * Level.levelnum + min(0.10, t.SpawnHealth() / 10000.0))
		{
			SpawnDrop("DR_PerkShard", t);
		}
	}

	void DropLoot(Actor t, Actor killer)
	{
		double r = frandom(0, 1);
		String cls;
		if (r < 0.50)
		{
			// ammo for something the player actually owns
			Array<String> opts;
			opts.Push("Clip");
			if (killer.FindInventory("Shotgun") || killer.FindInventory("SuperShotgun")) opts.Push("Shell");
			if (killer.FindInventory("RocketLauncher")) opts.Push("RocketAmmo");
			if (killer.FindInventory("PlasmaRifle") || killer.FindInventory("BFG9000")) opts.Push("Cell");
			cls = opts[random(0, opts.Size() - 1)];
		}
		else if (r < 0.75) cls = "HealthBonus";
		else if (r < 0.90) cls = "ArmorBonus";
		else cls = "Stimpack";
		SpawnDrop(cls, t);
	}

	void SpawnDrop(Class<Actor> cls, Actor t)
	{
		let a = Actor.Spawn(cls, t.pos + (0, 0, 24));
		if (!a) return;
		a.Vel = (frandom(-3, 3), frandom(-3, 3), frandom(3, 6));
		let inv = Inventory(a);
		if (inv) inv.bDropped = true;
	}

	// ------------------------------------------------------------------ death & victory

	override void PlayerDied(PlayerEvent e)
	{
		if (runOver) return;
		EndRun(false, players[e.PlayerNumber].mo);
	}

	void EndRun(bool won, Actor pmo)
	{
		runOver = true;
		victory = won;
		runOverTic = Level.totaltime;
		sumFloor = Level.levelnum;
		sumTime = Level.totaltime;
		let s = pmo ? DR_Stats(pmo.FindInventory("DR_Stats")) : null;
		if (s)
		{
			sumLevel = s.lvl;
			sumKills = s.kills;
			sumPerks = s.perksTaken;
			sumBest = s.bestWeapon;
			sumPerkList = "";
			for (int i = 0; i < DR_Perks.NUM_PERKS; i++)
			{
				if (s.stacks[i] <= 0) continue;
				if (sumPerkList.Length() > 0) sumPerkList = sumPerkList .. ", ";
				sumPerkList = sumPerkList .. DR_Perks.PerkName(i);
				if (s.stacks[i] > 1) sumPerkList = sumPerkList .. String.Format(" x%d", s.stacks[i]);
			}
		}
		// the launcher watches the log for this line
		Console.PrintfEx(PRINT_LOG, won ? "DR_RUN_OVER victory" : "DR_RUN_OVER death");
	}

	override void WorldTick()
	{
		if (runOver)
		{
			for (int i = 0; i < MAXPLAYERS; i++)
			{
				if (playeringame[i] && players[i].mo && players[i].health > 0)
					players[i].cheats |= CF_TOTALLYFROZEN;
			}
			return;
		}
		if (victorySectors.Size() == 0) return;
		let pmo = players[consoleplayer].mo;
		if (!pmo || pmo.health <= 0) return;
		if (victorySectors.Find(pmo.CurSector) == victorySectors.Size()) return;

		// gate stays sealed while the cyberdemon lives
		let ti = ThinkerIterator.Create("Cyberdemon");
		Actor m;
		while ((m = Actor(ti.Next())) != null)
		{
			if (m.health > 0)
			{
				if (Level.totaltime - sealedMsgTic > 70)
				{
					sealedMsgTic = Level.totaltime;
					let s = DR_Stats(pmo.FindInventory("DR_Stats"));
					if (s) s.ShowToast("\cgThe gate is sealed while the Cyberdemon lives.");
				}
				return;
			}
		}
		pmo.A_StartSound("misc/secret", CHAN_AUTO, CHANF_UI, 1.0, ATTN_NONE);
		EndRun(true, pmo);
	}

	// ------------------------------------------------------------------ net events

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "dr_perk")
		{
			let pmo = players[e.Player].mo;
			if (!pmo) return;
			let s = DR_Stats(pmo.FindInventory("DR_Stats"));
			if (s) s.ChoosePerk(e.Args[0]);
		}
	}

	// ------------------------------------------------------------------ UI driving

	override void UiTick()
	{
		if (gamestate != GS_LEVEL) return;
		if (Menu.GetCurrentMenu() != null) { uiDelay = 0; return; }
		uiDelay++;

		if (runOver)
		{
			if (Level.totaltime - runOverTic > 60 && uiDelay > 20) Menu.SetMenu('DR_RunOver');
			return;
		}
		let pmo = players[consoleplayer].mo;
		if (!pmo || pmo.health <= 0) return;
		let s = DR_Stats(pmo.FindInventory("DR_Stats"));
		if (s && s.offerActive && uiDelay > 25) Menu.SetMenu('DR_PerkMenu');
	}

	override void RenderOverlay(RenderEvent e)
	{
		DR_Hud.Draw(self, e);
	}
}
