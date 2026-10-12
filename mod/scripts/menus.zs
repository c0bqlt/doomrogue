// DoomRogue — perk choice menu and run summary menu

class DR_PerkMenu : GenericMenu
{
	int sel;
	double cardX[3], cardY, cardW, cardH;

	override void Init(Menu parent)
	{
		Super.Init(parent);
		sel = 1;
		DontDim = true;
		DontBlur = true;
	}

	DR_Stats GetStats()
	{
		let pmo = players[consoleplayer].mo;
		return pmo ? DR_Stats(pmo.FindInventory("DR_Stats")) : null;
	}

	int NumCards()
	{
		let s = GetStats();
		if (!s) return 0;
		int n = 0;
		for (int i = 0; i < 3; i++) if (s.offer[i] >= 0) n++;
		return n;
	}

	void Choose(int i)
	{
		if (i < 0 || i >= NumCards()) return;
		MenuSound("menu/choose");
		EventHandler.SendNetworkEvent("dr_perk", i);
		Close();
	}

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		int n = max(1, NumCards());
		switch (mkey)
		{
			case MKEY_Left:
			case MKEY_Up:
				sel = (sel + n - 1) % n;
				MenuSound("menu/cursor");
				return true;
			case MKEY_Right:
			case MKEY_Down:
				sel = (sel + 1) % n;
				MenuSound("menu/cursor");
				return true;
			case MKEY_Enter:
				Choose(sel);
				return true;
		}
		return Super.MenuEvent(mkey, fromcontroller);
	}

	override bool OnUIEvent(UIEvent ev)
	{
		if (ev.Type == UIEvent.Type_Char)
		{
			if (ev.KeyChar >= 0x31 && ev.KeyChar <= 0x33) { Choose(ev.KeyChar - 0x31); return true; }
		}
		else if (ev.Type == UIEvent.Type_MouseMove || ev.Type == UIEvent.Type_LButtonDown)
		{
			for (int i = 0; i < NumCards(); i++)
			{
				if (ev.MouseX >= cardX[i] && ev.MouseX <= cardX[i] + cardW && ev.MouseY >= cardY && ev.MouseY <= cardY + cardH)
				{
					sel = i;
					if (ev.Type == UIEvent.Type_LButtonDown) Choose(i);
					return true;
				}
			}
		}
		return Super.OnUIEvent(ev);
	}

	override void Ticker()
	{
		Super.Ticker();
		let s = GetStats();
		if (!s || !s.offerActive) Close();
	}

	override void Drawer()
	{
		let s = GetStats();
		if (!s) return;
		double sc = DR_Hud.Scale();
		double scrW = Screen.GetWidth(), scrH = Screen.GetHeight();
		Screen.Dim(Color(0, 0, 0), 0.65, 0, 0, int(scrW), int(scrH));

		DR_Hud.TxtCentered(BigFont, Font.CR_GOLD, scrH * 0.14, "LEVEL UP", sc * 1.4);
		DR_Hud.TxtCentered(SmallFont, Font.CR_GRAY, scrH * 0.14 + 30 * sc,
			String.Format("Level %d  -  choose a perk  (1 / 2 / 3, arrows + Enter, or click)", s.lvl), sc);

		int n = NumCards();
		cardW = 150 * sc;
		cardH = 130 * sc;
		double gap = 16 * sc;
		double total = n * cardW + (n - 1) * gap;
		double x0 = (scrW - total) / 2;
		cardY = scrH * 0.36;
		Font f = SmallFont;

		for (int i = 0; i < n; i++)
		{
			int p = s.offer[i];
			double cx = x0 + i * (cardW + gap);
			cardX[i] = cx;
			bool hot = (i == sel);
			int b = int(3 * sc);
			Color edge = hot ? Color(255, 255, 200, 40) : Color(255, 90, 90, 90);
			Screen.Clear(int(cx - b), int(cardY - b), int(cx + cardW + b), int(cardY + cardH + b), edge);
			Screen.Clear(int(cx), int(cardY), int(cx + cardW), int(cardY + cardH), hot ? Color(255, 50, 30, 20) : Color(255, 25, 20, 20));

			double ty = cardY + 8 * sc;
			String key = String.Format("[%d]", i + 1);
			DR_Hud.Txt(f, Font.CR_DARKGRAY, cx + 8 * sc, ty, key, sc);
			ty += 14 * sc;
			String nm = DR_Perks.PerkName(p);
			double nw = BigFont.StringWidth(nm) * sc * 0.8;
			double nsc = nw > cardW - 20 * sc ? sc * 0.8 * (cardW - 20 * sc) / nw : sc * 0.8;
			DR_Hud.Txt(BigFont, hot ? Font.CR_GOLD : Font.CR_WHITE, cx + 8 * sc, ty, nm, nsc);
			ty += 24 * sc;
			DR_Hud.Txt(f, Font.CR_TAN, cx + 8 * sc, ty, String.Format("Rank %d / %d", s.stacks[p] + 1, DR_Perks.PerkMax(p)), sc);
			ty += 16 * sc;
			Array<String> lines;
			DR_Perks.PerkDesc(p).Split(lines, "\n");
			foreach (l : lines)
			{
				DR_Hud.Txt(f, Font.CR_WHITE, cx + 8 * sc, ty, l, sc);
				ty += (f.GetHeight() + 2) * sc;
			}
		}
	}
}

class DR_RunOverMenu : OptionMenu
{
	override void Drawer()
	{
		let h = DR_Main(StaticEventHandler.Find("DR_Main"));
		double sc = DR_Hud.Scale();
		double scrH = Screen.GetHeight();
		Screen.Dim(Color(0, 0, 0), 0.75, 0, 0, Screen.GetWidth(), int(scrH));
		if (h)
		{
			bool won = h.victory;
			DR_Hud.TxtCentered(BigFont, won ? Font.CR_GOLD : Font.CR_RED, scrH * 0.08,
				won ? "VICTORY" : "YOU DIED", sc * 1.6);
			double y = scrH * 0.08 + 40 * sc;
			double lh = (SmallFont.GetHeight() + 4) * sc;
			int secs = h.sumTime / TICRATE;
			Array<String> rows;
			rows.Push(String.Format("Seed %d", h.seed));
			rows.Push(String.Format("Reached floor %d of %d", h.sumFloor, h.totalFloors));
			rows.Push(String.Format("Character level %d   -   %d kills", h.sumLevel, h.sumKills));
			rows.Push(String.Format("Time %d:%02d", secs / 60, secs % 60));
			if (h.sumBest.Length() > 0) rows.Push("Best weapon: " .. h.sumBest);
			rows.Push(h.sumPerkList.Length() > 0 ? "Perks: " .. h.sumPerkList : "Perks: none");
			foreach (r : rows)
			{
				DR_Hud.TxtCentered(SmallFont, Font.CR_WHITE, y, r, sc);
				y += lh;
			}
			DR_Hud.TxtCentered(SmallFont, Font.CR_DARKGRAY, y + lh, "Permadeath: this dungeon is gone.", sc);
		}
		mDesc.mPosition = int(scrH * 0.72);
		Super.Drawer();
	}

	override bool MenuEvent(int mkey, bool fromcontroller)
	{
		// no backing out of the summary
		if (mkey == MKEY_Back) return true;
		return Super.MenuEvent(mkey, fromcontroller);
	}
}
