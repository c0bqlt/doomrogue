// DoomRogue — overlay HUD

class DR_Hud ui
{
	static double Scale()
	{
		return max(1.0, Screen.GetHeight() / 480.0);
	}

	static void Txt(Font f, int col, double x, double y, String s, double sc, double alpha = 1.0)
	{
		Screen.DrawText(f, col, x, y, s, DTA_ScaleX, sc, DTA_ScaleY, sc, DTA_Alpha, alpha);
	}

	static void TxtCentered(Font f, int col, double y, String s, double sc, double alpha = 1.0)
	{
		double w = f.StringWidth(s) * sc;
		Txt(f, col, (Screen.GetWidth() - w) / 2, y, s, sc, alpha);
	}

	static void Draw(DR_Main h, RenderEvent e)
	{
		if (gamestate != GS_LEVEL) return;
		let pmo = players[consoleplayer].mo;
		if (!pmo) return;
		let s = DR_Stats(pmo.FindInventory("DR_Stats"));
		if (!s) return;

		// stay out of the way while a menu (perk choice / summary) is on screen
		if (Menu.GetCurrentMenu() != null) return;

		double sc = Scale();
		Font f = SmallFont;
		double lh = (f.GetHeight() + 2) * sc;
		double x = 10 * sc, y = Screen.GetHeight() * 0.20;
		int now = Level.totaltime;

		// panel background
		Screen.Dim(Color(0, 0, 0), 0.45, int(x - 4 * sc), int(y - 4 * sc), int(170 * sc), int(lh * 5 + 8 * sc));

		Txt(f, Font.CR_GOLD, x, y, String.Format("FLOOR %d / %d", Level.levelnum, h.totalFloors), sc);
		y += lh;

		// level + xp bar
		Txt(f, Font.CR_WHITE, x, y, String.Format("LV %d", s.lvl), sc);
		double bx = x + 40 * sc, bw = 118 * sc, bh = 5 * sc, by = y + 1 * sc;
		double frac = clamp(double(s.xp) / DR_Stats.XPForLevel(s.lvl), 0.0, 1.0);
		Screen.Clear(int(bx), int(by), int(bx + bw), int(by + bh), Color(255, 40, 40, 40));
		Screen.Clear(int(bx), int(by), int(bx + bw * frac), int(by + bh), Color(255, 230, 180, 40));
		y += lh;

		Txt(f, Font.CR_GRAY, x, y, String.Format("Kills %d   Perks %d", s.kills, s.perksTaken), sc);
		y += lh;

		// perk summary
		String perks = "";
		for (int i = 0; i < DR_Perks.NUM_PERKS; i++)
		{
			if (s.stacks[i] <= 0) continue;
			perks = perks .. DR_Perks.PerkShort(i) .. (s.stacks[i] > 1 ? String.Format("%d ", s.stacks[i]) : " ");
		}
		if (perks.Length() == 0) perks = "no perks yet";
		Txt(f, Font.CR_TAN, x, y, perks, sc * 0.85);
		y += lh;

		// current weapon rarity
		int wi = s.CurWeaponIndex();
		if (wi >= 0)
		{
			int r = s.wRarity[wi];
			String w = DR_Perks.RarityColorCode(r) .. DR_Perks.RarityName(r) .. "\c- " .. players[consoleplayer].ReadyWeapon.GetTag();
			if (s.wDmg[wi] > 0) w = w .. String.Format(" +%d%%", int(s.wDmg[wi] * 100 + 0.5));
			Txt(f, Font.CR_WHITE, x, y, w, sc * 0.85);
		}
		else
		{
			Txt(f, Font.CR_DARKGRAY, x, y, "Common weapon", sc * 0.85);
		}

		// pending perk hint
		if (s.pendingPerks > 0 && !h.runOver)
		{
			TxtCentered(f, Font.CR_GOLD, Screen.GetHeight() * 0.18, "PERK CHOICE PENDING", sc);
		}

		// floor title
		int ft = now - h.floorStartTic;
		if (ft < 140 && !h.runOver)
		{
			double a = ft < 105 ? 1.0 : (140 - ft) / 35.0;
			TxtCentered(BigFont, Font.CR_RED, Screen.GetHeight() * 0.28, h.floorTitle, sc, a);
		}

		// level up flash
		int lt = now - s.levelUpTic;
		if (s.levelUpTic > 0 && lt < 60)
		{
			TxtCentered(BigFont, Font.CR_GOLD, Screen.GetHeight() * 0.38, "LEVEL UP!", sc, 1.0 - lt / 60.0);
		}

		// crit indicator near the crosshair
		if (s.critTic > 0 && now - s.critTic < 12)
		{
			TxtCentered(f, Font.CR_RED, Screen.GetHeight() * 0.5 + 12 * sc, "CRIT!", sc, 1.0 - (now - s.critTic) / 12.0);
		}

		// toast
		int tt = now - s.toastTic;
		if (s.toastTic > 0 && tt < 175 && s.toast.Length() > 0)
		{
			double a = tt < 140 ? 1.0 : (175 - tt) / 35.0;
			TxtCentered(f, Font.CR_WHITE, Screen.GetHeight() * 0.66, s.toast, sc, a);
		}

		// death / victory banner before the menu appears
		if (h.runOver)
		{
			TxtCentered(BigFont, h.victory ? Font.CR_GOLD : Font.CR_RED, Screen.GetHeight() * 0.35,
				h.victory ? "VICTORY" : "YOU DIED", sc * 1.5);
		}
	}
}
