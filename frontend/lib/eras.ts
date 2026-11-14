import type { EraId, EraInfo } from "./types";

// The five eras from the plan's Odyssey Map. Person D's lore JSON is the source of truth
// for the copy — update blurbs to match it.
export const ERAS: EraInfo[] = [
  { id: "2010_trickshots", year: "2010", label: "Trickshots", blurb: "Where it began: Call of Duty trickshot montages." },
  { id: "2013_rug", year: "2013", label: "Rug Era", blurb: "Vlogs, the house, FaZe becomes a lifestyle." },
  { id: "2020_nuke", year: "2020", label: "Nuke Squad", blurb: "Warzone takeover and a new generation of members." },
  { id: "2022_snoop", year: "2022", label: "Snoop", blurb: "Snoop Dogg joins the board. FaZe goes mainstream." },
  { id: "today", year: "Today", label: "Ithaca", blurb: "The road home. Your chapter starts now." },
];

export const eraById = (id: EraId) => ERAS.find((e) => e.id === id) ?? ERAS[0];
