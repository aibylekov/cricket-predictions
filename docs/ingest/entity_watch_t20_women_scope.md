# Entity watch — L1 rebuild (2026-10-23T11:59:34)

- previous dims: `C:\Users\Corsair\AppData\Local\Temp\claude\C--Users-Corsair-cricket-predictions\486a79c6-e372-421a-8990-caf9ca64694d\scratchpad\l1_before`
- current L1: `C:\Users\Corsair\cricket-predictions\data\lake\l1`
- rule: nothing below was merged or dropped automatically; candidates are listed for a human decision (bridge_entity style).

## 0. Match deltas (dim_match)

| gender | matches | completed | matches_before | completed_before |
|---|---|---|---|---|
| female | 1424 | 1406 | 0 | 0 |
| male | 4748 | 4601 | 4748 | 4601 |

- matches REMOVED vs before: 0

status by gender:

| gender | status | n |
|---|---|---|
| female | completed | 1406 |
| female | not_started | 18 |
| male | completed | 4601 |
| male | not_started | 146 |
| male | started | 1 |

## 1. Teams

- dim_team rows: 531 before -> 716 now; NEW: 185
- team_id_map: 734 scoped ids, 18 duplicate ids remapped to a canonical id

### 1a. New teams entering L1

| team_id | team_name | team_key | gender | is_national | country_code | matches | dedupe_status | duplicate_ids_remapped_in |
|---|---|---|---|---|---|---|---|---|
| 136 | South Africa Women | rsaw | female | 1 | ZAF | 61 | canonical (single id) |  |
| 79 | England Women | engw | female | 1 | GBR | 60 | canonical (single id) |  |
| 242 | India Women | indw | female | 1 | IND | 56 | canonical (single id) |  |
| 42 | Sri Lanka Women | slw | female | 1 | LKA | 55 | canonical (single id) |  |
| 193 | Brisbane Heat Women | bhw | female | 0 |  | 55 | canonical (single id) |  |
| 43 | Bangladesh Women | banw | female | 1 | BGD | 54 | canonical (single id) |  |
| 295 | Thailand Women | c__team__thaw__601c7 | female | 1 | THA | 54 | canonical (single id) |  |
| 135 | Pakistan Women | pakw | female | 1 | PAK | 53 | canonical (single id) |  |
| 149 | New Zealand Women | nzw | female | 1 | NZL | 53 | canonical (single id) |  |
| 195 | Perth Scorchers Women | perw | female | 0 |  | 53 | canonical (single id) |  |
| 194 | Hobart Hurricanes Women | hbhw | female | 0 |  | 52 | canonical (single id) |  |
| 130 | Netherlands Women | nlw | female | 1 | NLD | 50 | canonical (single id) |  |
| 197 | Sydney Thunder Women | sytw | female | 0 |  | 50 | canonical (single id) |  |
| 190 | Sydney Sixers Women | sydw | female | 0 |  | 49 | canonical (single id) |  |
| 196 | Adelaide Strikers Women | adsw | female | 0 |  | 49 | canonical (single id) |  |
| 148 | West Indies Women | wiw | female | 1 | WIN | 48 | canonical (single id) |  |
| 191 | Melbourne Stars Women | mlsw | female | 0 |  | 48 | canonical (single id) |  |
| 192 | Melbourne Renegades Women | mlrw | female | 0 |  | 48 | canonical (single id) |  |
| 80 | Australia Women | ausw | female | 1 | AUS | 46 | canonical (single id) |  |
| 131 | Ireland Women  | irew | female | 1 | IRL | 43 | canonical (single id) |  |
| 297 | Scotland Women  | c__team__scotland_women__87944 | female | 1 | GBR | 42 | canonical (single id) |  |
| 296 | United Arab Emirates Women | c__team__uaew__67faf | female | 1 | ARE | 39 | canonical (single id) |  |
| 312 | Nepal Women | nepw | female | 1 | NPL | 38 | canonical (absorbed duplicates) | 1006 |
| 273 | Delhi Capitals Women | c__team__dcw__5bd62 | female | 0 | IND | 28 | canonical (single id) |  |
| 301 | United States Of America Women | c__team__usaw__42e70 | female | 1 | USA | 28 | canonical (single id) |  |
| 519 | Warwickshire Women | a-rz--cricket--ww-N5XF | female | 0 |  | 28 | canonical (single id) |  |
| 522 | The Blaze Women | c__team__lit__e0ede | female | 0 |  | 28 | canonical (single id) |  |
| 527 | Surrey Women | c__team__surw__8a012 | female | 0 |  | 28 | canonical (single id) |  |
| 274 | Mumbai Indians Women | c__team__miw__37fe2 | female | 0 | IND | 27 | canonical (single id) |  |
| 275 | Royal Challengers Bangalore Women | c__team__rcbw__878bd | female | 0 | IND | 27 | canonical (single id) |  |
| 313 | Malaysia Women | c__team__malw__02c45 | female | 1 | MYS | 27 | canonical (single id) |  |
| 520 | Hampshire Women | c__team__hamw__7f89a | female | 0 |  | 27 | canonical (single id) |  |
| 521 | Durham Women | a-rz--cricket--akp-oi3J | female | 0 | GBR | 27 | canonical (single id) |  |
| 277 | Gujarat Giants Women | c__team__ggw__518ce | female | 0 | IND | 26 | canonical (single id) |  |
| 528 | Somerset Women | a-rz--cricket--sw-LtSu | female | 0 | GBR | 26 | canonical (single id) |  |
| 529 | Essex Women | c__team__essw__bd362 | female | 0 |  | 26 | canonical (single id) |  |
| 540 | Lancashire Women | a-rz--cricket--lw-XuU3 | female | 0 | GBR | 26 | canonical (single id) |  |
| 132 | Barbados Royals | brw | female | 0 | WIN | 25 | canonical (absorbed duplicates) | 316 |
| 133 | Guyana Amazon Warriors | gaww | female | 0 | WIN | 24 | canonical (absorbed duplicates) | 317 |
| 276 | UP Warriorz Women | c__team__upww__d527d | female | 0 | IND | 24 | canonical (single id) |  |
| 439 | Wellington Blaze | c__team__wb__d96a8 | female | 0 | NZL | 23 | canonical (single id) |  |
| 299 | Zimbabwe Women | zimw | female | 1 | ZWE | 22 | canonical (single id) |  |
| 434 | Northern Brave | c__team__nbw__bf242 | female | 0 | NZL | 22 | canonical (single id) |  |
| 435 | Auckland Hearts | c__team__adh__d7a8e | female | 0 | NZL | 22 | canonical (single id) |  |
| 134 | Trinbago Knight Riders | tkrw | female | 0 | WIN | 21 | canonical (absorbed duplicates) | 318 |
| 314 | Papua New Guinea Women | c__team__pngw__89f95 | female | 1 | PNG | 21 | canonical (single id) |  |
| 436 | Otago Sparks | c__team__os__1b53e | female | 0 | NZL | 21 | canonical (single id) |  |
| 437 | Canterbury Magicians | c__team__cm__33a33 | female | 0 | NZL | 20 | canonical (single id) |  |
| 438 | Central Hinds | c__team__ch__f9464 | female | 0 | NZL | 20 | canonical (single id) |  |
| 605 | Indonesia Women | c__team__inaw__75185 | female | 1 | IDN | 20 | canonical (single id) |  |
| 300 | Vanuatu Women | c__team__vanw__32518 | female | 0 | VUT | 17 | canonical (single id) |  |
| 448 | India Women U19 | c__team__indwu19__bb8ec | female | 1 | IND | 17 | canonical (single id) |  |
| 298 | Uganda Women | c__team__ugaw__92901 | female | 1 | UGA | 16 | canonical (single id) |  |
| 582 | Philippines Women | c__team__phpsw__c1c90 | female | 1 | PHL | 16 | canonical (single id) |  |
| 1004 | Rwanda Women | c__team__rwaw__84521 | female | 1 | RWA | 16 | canonical (single id) |  |
| 579 | Japan Women | c__team__jpnw__5e79f | female | 1 | JPN | 15 | canonical (single id) |  |
| 881 | Oman Women | c__team__oma_w__9fc0f | female | 1 | OMN | 15 | canonical (single id) |  |
| 457 | South Africa Women U19 | c__team__south_africa_women_u19__97046 | female | 1 | ZAF | 14 | canonical (single id) |  |
| 560 | Hong Kong Women | hkgw | female | 1 |  | 14 | canonical (single id) |  |
| 828 | Namibia Women | c__team__namw__bace7 | female | 1 | NAM | 14 | canonical (single id) |  |
| 446 | Sri Lanka Women U19 | c__team__slwu19__da1c9 | female | 1 | LKA | 13 | canonical (single id) |  |
| 561 | Bahrain Women | c__team__bhnw__683a7 | female | 1 | BHR | 13 | canonical (single id) |  |
| 562 | Bhutan Women | c__team__btnw__ce36c | female | 1 | BTN | 13 | canonical (single id) |  |
| 581 | China Women | c__team__chiw__a4db9 | female | 1 | CHN | 13 | canonical (single id) |  |
| 305 | Hong Kong, China Women | c__team__hkgw__892e7 | female | 1 | HKG | 12 | canonical (single id) |  |
| 450 | England Women U19 | c__team__engwu19__f305d | female | 1 | GBR | 12 | canonical (single id) |  |
| 458 | Australia Women U19 | c__team__auswu19__464ba | female | 1 | AUS | 12 | canonical (single id) |  |
| 541 | Gauhati Town Club Women | a-rz--cricket--gtcw-D2jy | female | 0 | IND | 12 | canonical (single id) |  |
| 542 | 91 Yards Club Women | a-rz--cricket--9ycw-7Z3A | female | 0 | IND | 12 | canonical (single id) |  |
| 559 | Kuwait Women | c__team__kwtw__e1d78 | female | 1 | KWT | 12 | canonical (single id) |  |
| 563 | Qatar Women  | c__team__qtrw__2830d | female | 1 | QAT | 12 | canonical (single id) |  |
| 604 | Singapore Women | c__team__sinw__33ff3 | female | 1 | SGP | 12 | canonical (single id) |  |
| 738 | ACT Meteors Women | c__team__act__514fc | female | 0 | AUS | 12 | canonical (absorbed duplicates) | 353 |
| 818 | Tanzania Women | c__team__tanw__1ff47 | female | 1 | TZA | 12 | canonical (single id) |  |
| 841 | Myanmar Women | c__team__mnrw__c7604 | female | 1 | MMR | 12 | canonical (single id) |  |
| 1003 | Yorkshire Women | a-rz--cricket--YKW | female | 0 | GBR | 12 | canonical (single id) |  |
| 544 | S.G.Club Women | a-rz--cricket--sw-xrX1 | female | 0 | IND | 11 | canonical (single id) |  |
| 545 | Maharana AC Women | a-rz--cricket--maw-jW1M | female | 0 | IND | 11 | canonical (single id) |  |
| 740 | Lions Women | a-rz--cricket--lw-Sz0Y | female | 0 | ZAF | 11 | canonical (single id) |  |
| 743 | Western Province Women | a-rz--cricket--wpw-4InJ | female | 0 | ZAF | 11 | canonical (single id) |  |
| 449 | West Indies Women U19 | c__team__wiwu19__c8d1c | female | 1 | WIN | 10 | canonical (single id) |  |
| 451 | Ireland Women U19 | c__team__irewu19__bf4d9 | female | 1 | IRL | 10 | canonical (single id) |  |
| 453 | United States Of America Women U19 | a-rz--cricket--usoawu-sGfq | female | 1 | USA | 10 | canonical (single id) |  |
| 455 | Nigeria Women U19 | a-rz--cricket--nwu-A83c | female | 1 | NGA | 10 | canonical (single id) |  |
| 456 | New Zealand Women U19 | c__team__nzw19__6ec34 | female | 1 | NZL | 10 | canonical (single id) |  |
| 459 | Scotland Women U19 | c__team__sctwu19__377d0 | female | 1 | GBR | 10 | canonical (single id) |  |
| 460 | Bangladesh Women U19 | c__team__banwu19__39e01 | female | 1 | BGD | 10 | canonical (single id) |  |
| 543 | Rising Star Women | a-rz--cricket--rsw-pFnH | female | 0 | IND | 10 | canonical (single id) |  |
| 546 | Warriors Women | c__team__wrsw__8c5a9 | female | 0 | HKG | 10 | canonical (single id) |  |
| 741 | Dolphins Women | a-rz--cricket--dw-cZ0k | female | 0 | ZAF | 10 | canonical (single id) |  |
| 742 | South Western Districts Women | a-rz--cricket--swdw-qDsj | female | 0 | ZAF | 10 | canonical (single id) |  |
| 744 | North West Women | a-rz--cricket--nww-b2Bp | female | 0 | ZAF | 10 | canonical (single id) |  |
| 745 | Titans Women | a-rz--cricket--tw-UP5s | female | 0 | ZAF | 10 | canonical (single id) |  |
| 758 | Madhya Pradesh Womens | c__team__mpdw__deeca | female | 0 | IND | 10 | canonical (single id) |  |
| 798 | Canada Women | c__team__canw__1be8d | female | 1 | CAN | 10 | canonical (single id) |  |
| 1086 | Gloucestershire Women | a-rz--cricket--gw-OkY8 | female | 0 | GBR | 10 | canonical (single id) |  |
| 882 | Saudi Arabia Women | c__team__sarw__2f87b | female | 1 | SAU | 9 | canonical (single id) |  |
| 1081 | Kent Women | c__team__ketw__c0ed6 | female | 0 |  | 9 | canonical (single id) |  |
| 1087 | Glamorgan Women | a-rz--cricket--gw-C6Sw | female | 0 | GBR | 9 | canonical (single id) |  |
| 1221 | Nigeria Women | c__team__nigw__857b9 | female | 1 | NGA | 9 | canonical (single id) |  |
| 447 | Malaysia Women U19 | a-rz--cricket--mwu-6cs5 | female | 1 | MYS | 8 | canonical (single id) |  |
| 452 | Pakistan Women U19 | c__team__pakwu19__200e7 | female | 1 | PAK | 8 | canonical (single id) |  |
| 454 | Samoa Women U19 | a-rz--cricket--swu-FzY8 | female | 1 | WSM | 8 | canonical (single id) |  |
| 461 | Nepal Women U19 | a-rz--cricket--nwu-RxwM | female | 1 | NPL | 8 | canonical (single id) |  |
| 580 | Mongolia Women | c__team__mngw__6e6d1 | female | 1 | MNG | 8 | canonical (single id) |  |
| 739 | India A Women | c__team__ind_a_w__7018a | female | 1 | IND | 8 | canonical (single id) |  |
| 756 | Mumbai Womens | c__team__mumw__89a41 | female | 0 | IND | 8 | canonical (single id) |  |
| 922 | Denmark Women | c__team__denw__85816 | female | 0 | DNK | 8 | canonical (single id) |  |
| 1005 | Italy Women | c__team__itaw__a4e49 | female | 1 | ITA | 8 | canonical (single id) |  |
| 1080 | Middlesex Women | c__team__midw__2ea14 | female | 0 |  | 8 | canonical (single id) |  |
| 1082 | Derbyshire Women | a-rz--cricket--dw-s7lv | female | 0 | GBR | 8 | canonical (single id) |  |
| 1083 | Sussex Women | c__team__susw__1bb13 | female | 0 |  | 8 | canonical (single id) |  |
| 1084 | Leicestershire Women | a-rz--cricket--lw-f7ZW | female | 0 | GBR | 8 | canonical (single id) |  |
| 1085 | Worcestershire Women | a-rz--cricket--ww-Ocjd | female | 0 | GBR | 8 | canonical (single id) |  |
| 1088 | Northamptonshire Women | a-rz--cricket--nw-mhp3 | female | 0 | GBR | 8 | canonical (single id) |  |
| 1222 | Malawi Women | c__team__mww__1f3b0 | female | 1 | MWI | 8 | canonical (single id) |  |
| 1223 | Brazil Women | c__team__brzw__c5c4f | female | 1 | BRA | 8 | canonical (single id) |  |
| 762 | Karnataka Womens | c__team__karw__516c4 | female | 0 | IND | 7 | canonical (single id) |  |
| 925 | Sri Lanka A Women | c__team__slaw__3657b | female | 1 | LKA | 7 | canonical (single id) |  |
| 1224 | Zimbabwe HPC Women | a-rz--cricket--zhw-zpkR | female | 0 | ZWE | 7 | canonical (single id) |  |
| 751 | Maharashtra Womens | c__team__mahw__cddfd | female | 0 | IND | 6 | canonical (single id) |  |
| 752 | Tamil Nadu Womens | c__team__tnw__c6bb0 | female | 0 | IND | 6 | canonical (single id) |  |
| 766 | Delhi Womens | c__team__dliw__c63de | female | 0 | IND | 6 | canonical (single id) |  |
| 772 | Vidarbha Womens | c__team__vdbw__31f94 | female | 0 | IND | 6 | canonical (single id) |  |
| 809 | West Zone Women | c__team__wezw__342fe | female | 0 | IND | 6 | canonical (single id) |  |
| 810 | North Zone Women | c__team__nozw__0ecbb | female | 0 | IND | 6 | canonical (single id) |  |
| 895 | Windward Islands Women | c__team__wniw__622b5 | female | 0 | WIN | 6 | canonical (single id) |  |
| 896 | Guyana Women | c__team__guyw__8e67c | female | 0 | WIN | 6 | canonical (single id) |  |
| 897 | Jamaica Women | c__team__jcw__296d0 | female | 0 | WIN | 6 | canonical (single id) |  |
| 898 | Leeward Islands Women | c__team__lwiw__a92f1 | female | 0 | WIN | 6 | canonical (single id) |  |
| 899 | Trinidad & Tobago Women | c__team__ttw__cf987 | female | 0 | WIN | 6 | canonical (single id) |  |
| 900 | Barbados Women | c__team__bbdw__1d094 | female | 0 | WIN | 6 | canonical (single id) |  |
| 1041 | Dragons Women | c__team__dgw__b962d | female | 0 | IRL | 6 | canonical (single id) |  |
| 1042 | Typhoons Women | c__team__typw__b63cf | female | 0 | IRL | 6 | canonical (single id) |  |
| 1183 | Gwalior Shernis Women | a-rz--cricket--gsw-OBdP | female | 0 | IND | 6 | canonical (single id) |  |
| 713 | Fiji Women | c__team__fijw__fa105 | female | 1 |  | 5 | canonical (single id) |  |
| 714 | Cook Islands Women | c__team__cokw__03549 | female | 1 | COK | 5 | canonical (single id) |  |
| 715 | Samoa Women | c__team__samw__62151 | female | 1 | WSM | 5 | canonical (single id) |  |
| 747 | Kerala Womens | c__team__kerw__bcf20 | female | 0 | IND | 5 | canonical (single id) |  |
| 748 | Uttar Pradesh Womens | c__team__upw__55d2c | female | 0 | IND | 5 | canonical (single id) |  |
| 759 | Andhra Womens | c__team__andw__3bc14 | female | 0 | IND | 5 | canonical (single id) |  |
| 780 | Haryana Womens | c__team__harw__c0fdc | female | 0 | IND | 5 | canonical (single id) |  |
| 808 | North East Zone Women | c__team__nezw__286e9 | female | 0 | IND | 5 | canonical (single id) |  |
| 811 | South Zone Women | c__team__sozw__e7bee | female | 0 | IND | 5 | canonical (single id) |  |
| 812 | Central Zone Women | c__team__cezw__04ad1 | female | 0 |  | 5 | canonical (single id) |  |
| 813 | East Zone Women | c__team__eazw__691f8 | female | 0 | IND | 5 | canonical (single id) |  |
| 924 | Bangladesh A Women | c__team__banaw__09a77 | female | 1 | BGD | 5 | canonical (single id) |  |
| 1111 | SoBo Mumbai Falcons Women | a-rz--cricket--smfw-xvjL | female | 0 | IND | 5 | canonical (single id) |  |
| 1112 | Aakash Tigers MWS Women | a-rz--cricket--atmw-KNDS | female | 0 | IND | 5 | canonical (single id) |  |
| 1182 | Chambal Ghariyals Women | a-rz--cricket--cgw-q8RP | female | 0 | IND | 5 | canonical (single id) |  |
| 1185 | Bundelkhand Bulls Women | a-rz--cricket--bbw-c2MR | female | 0 | IND | 5 | canonical (single id) |  |
| 1192 | NECO Master Blaster Women | a-rz--cricket--nmbw-z8Mt | female | 0 | IND | 5 | canonical (single id) |  |
| 664 | South Delhi Superstarz Women | a-rz--cricket--sdsw-M6XW | female | 0 | IND | 4 | canonical (single id) |  |
| 667 | Central Delhi Queens Women | a-rz--cricket--cdqw-dq1f | female | 0 | IND | 4 | canonical (single id) |  |
| 749 | Punjab Womens | c__team__punw__f4ebc | female | 0 | IND | 4 | canonical (single id) |  |
| 750 | Saurashtra Womens | c__team__srtw__bb898 | female | 0 | IND | 4 | canonical (single id) |  |
| 757 | Bengal Womens | c__team__ben__4884b | female | 0 | IND | 4 | canonical (single id) |  |
| 763 | Baroda Womens | c__team__bcaw__3f94d | female | 0 | IND | 4 | canonical (single id) |  |
| 782 | Railways Womens | c__team__rsww__f756d | female | 0 | IND | 4 | canonical (single id) |  |
| 923 | Pakistan A Women  | c__team__pakwa__b8ab4 | female | 1 | PAK | 4 | canonical (single id) |  |
| 1110 | Thane Sky Risers Women | a-rz--cricket--tsw-j63B | female | 0 | IND | 4 | canonical (single id) |  |
| 1184 | Bhopal Wolves Women | a-rz--cricket--bww-ank6 | female | 0 | IND | 4 | canonical (single id) |  |
| 1186 | Royal Nimar Eagles Women | a-rz--cricket--rnew-5CyT | female | 0 | IND | 4 | canonical (single id) |  |
| 1194 | Orange Tigersses Women  | a-rz--cricket--otw-2sKm | female | 0 | IND | 4 | canonical (single id) |  |
| 1195 | India Warriors Women | a-rz--cricket--iww-cuZe | female | 0 | IND | 4 | canonical (single id) |  |
| 1277 | Switzerland Women | a-rz--cricket--sw-GKEg | female | 1 | EUR | 4 | canonical (single id) |  |
| 665 | North Delhi Strikers Women | a-rz--cricket--ndsw-jeDd | female | 0 | IND | 3 | canonical (single id) |  |
| 666 | East Delhi Riders Women | a-rz--cricket--edrw-sBC2 | female | 0 | IND | 3 | canonical (single id) |  |
| 755 | Jammu and Kashmir Womens | c__team__jkrw__844d4 | female | 0 | IND | 3 | canonical (single id) |  |
| 761 | Himachal Pradesh Womens | c__team__hphw__59a11 | female | 0 | IND | 3 | canonical (single id) |  |
| 764 | Rajasthan Womens | c__team__rjsw__b0d45 | female | 0 | IND | 3 | canonical (single id) |  |
| 775 | Odisha Womens | c__team__odisha_womens__8c7d7 | female | 0 | IND | 3 | canonical (single id) |  |
| 1078 | New Zealand Women A | a-rz--cricket--nzwa-1CLK | female | 0 | NZL | 3 | canonical (single id) |  |
| 1193 | Pagariya Strikers Nagpur Women | a-rz--cricket--psnw-jLMK | female | 0 | IND | 3 | canonical (single id) |  |
| 1243 | England A Women | c__team__engwa__90dc0 | female | 1 | GBR | 3 | canonical (single id) |  |
| 753 | Goa Womens | c__team__goam__b3102 | female | 0 | IND | 2 | canonical (single id) |  |
| 754 | Uttarakhand Womens | c__team__utkw__868bc | female | 0 | IND | 2 | canonical (single id) |  |
| 760 | Chhattisgarh Womens | c__team__ctgw__c89d9 | female | 0 |  | 2 | canonical (single id) |  |
| 773 | Hyderabad Womens | c__team__hdbw__5d666 | female | 0 |  | 2 | canonical (single id) |  |
| 774 | Chandigarh Women CC | c__team__cwcc__7e6d4 | female | 0 | IND | 2 | canonical (single id) |  |
| 776 | Gujarat Womens | c__team__glw__69fac | female | 0 | IND | 2 | canonical (single id) |  |
| 781 | Jharkhand Women | c__team__jharkhand_womens__6932e | female | 0 | IND | 2 | canonical (single id) |  |
| 777 | Bihar Womens | c__team__bihw__28492 | female | 0 | IND | 1 | canonical (single id) |  |
| 778 | Pondicherry Womens | c__team__pdcw__5daf5 | female | 0 | IND | 1 | canonical (single id) |  |
| 779 | Tripura Womens | c__team__traw__81a47 | female | 0 | IND | 1 | canonical (single id) |  |

### 1b. Possible duplicates for review (NOT merged): new team vs existing team with the same base name once women/w are stripped

- same-gender candidates (two ids that MAY be one side): 82 rows below; token-subset rows are mostly senior vs A / U19 / franchise vs state (distinct) — only 'exact' rows are likely duplicates
- cross-gender pairs (men's club + its women's side, e.g. 'Perth Scorchers' vs 'Perth Scorchers Women'): 272 — expected, distinct teams, not listed

| new_team_id | new_team | new_gender | candidate_id | candidate | candidate_gender | candidate_matches | relation |
|---|---|---|---|---|---|---|---|
| 80 | Australia Women | female | 458 | Australia Women U19 | female | 12 | token subset |
| 458 | Australia Women U19 | female | 80 | Australia Women | female | 46 | token subset |
| 924 | Bangladesh A Women | female | 43 | Bangladesh Women | female | 54 | token subset |
| 43 | Bangladesh Women | female | 460 | Bangladesh Women U19 | female | 10 | token subset |
| 43 | Bangladesh Women | female | 924 | Bangladesh A Women | female | 5 | token subset |
| 460 | Bangladesh Women U19 | female | 43 | Bangladesh Women | female | 54 | token subset |
| 132 | Barbados Royals | female | 900 | Barbados Women | female | 6 | token subset |
| 900 | Barbados Women | female | 132 | Barbados Royals | female | 25 | token subset |
| 667 | Central Delhi Queens Women | female | 766 | Delhi Womens | female | 6 | token subset |
| 581 | China Women | female | 305 | Hong Kong, China Women | female | 12 | token subset |
| 273 | Delhi Capitals Women | female | 766 | Delhi Womens | female | 6 | token subset |
| 766 | Delhi Womens | female | 273 | Delhi Capitals Women | female | 28 | token subset |
| 766 | Delhi Womens | female | 664 | South Delhi Superstarz Women | female | 4 | token subset |
| 766 | Delhi Womens | female | 665 | North Delhi Strikers Women | female | 3 | token subset |
| 766 | Delhi Womens | female | 666 | East Delhi Riders Women | female | 3 | token subset |
| 766 | Delhi Womens | female | 667 | Central Delhi Queens Women | female | 4 | token subset |
| 666 | East Delhi Riders Women | female | 766 | Delhi Womens | female | 6 | token subset |
| 813 | East Zone Women | female | 808 | North East Zone Women | female | 5 | token subset |
| 1243 | England A Women | female | 79 | England Women | female | 60 | token subset |
| 79 | England Women | female | 450 | England Women U19 | female | 12 | token subset |
| 79 | England Women | female | 1243 | England A Women | female | 3 | token subset |
| 450 | England Women U19 | female | 79 | England Women | female | 60 | token subset |
| 277 | Gujarat Giants Women | female | 776 | Gujarat Womens | female | 2 | token subset |
| 776 | Gujarat Womens | female | 277 | Gujarat Giants Women | female | 26 | token subset |
| 133 | Guyana Amazon Warriors | female | 546 | Warriors Women | female | 10 | token subset |
| 133 | Guyana Amazon Warriors | female | 896 | Guyana Women | female | 6 | token subset |
| 896 | Guyana Women | female | 133 | Guyana Amazon Warriors | female | 24 | token subset |
| 560 | Hong Kong Women | female | 305 | Hong Kong, China Women | female | 12 | token subset |
| 305 | Hong Kong, China Women | female | 560 | Hong Kong Women | female | 14 | token subset |
| 305 | Hong Kong, China Women | female | 581 | China Women | female | 13 | token subset |
| 739 | India A Women | female | 242 | India Women | female | 56 | token subset |
| 1195 | India Warriors Women | female | 242 | India Women | female | 56 | token subset |
| 1195 | India Warriors Women | female | 546 | Warriors Women | female | 10 | token subset |
| 242 | India Women | female | 448 | India Women U19 | female | 17 | token subset |
| 242 | India Women | female | 739 | India A Women | female | 8 | token subset |
| 242 | India Women | female | 1195 | India Warriors Women | female | 4 | token subset |
| 448 | India Women U19 | female | 242 | India Women | female | 56 | token subset |
| 131 | Ireland Women  | female | 451 | Ireland Women U19 | female | 10 | token subset |
| 451 | Ireland Women U19 | female | 131 | Ireland Women  | female | 43 | token subset |
| 313 | Malaysia Women | female | 447 | Malaysia Women U19 | female | 8 | token subset |
| 447 | Malaysia Women U19 | female | 313 | Malaysia Women | female | 27 | token subset |
| 274 | Mumbai Indians Women | female | 756 | Mumbai Womens | female | 8 | token subset |
| 756 | Mumbai Womens | female | 274 | Mumbai Indians Women | female | 27 | token subset |
| 756 | Mumbai Womens | female | 1111 | SoBo Mumbai Falcons Women | female | 5 | token subset |
| 312 | Nepal Women | female | 461 | Nepal Women U19 | female | 8 | token subset |
| 461 | Nepal Women U19 | female | 312 | Nepal Women | female | 38 | token subset |
| 149 | New Zealand Women | female | 456 | New Zealand Women U19 | female | 10 | token subset |
| 149 | New Zealand Women | female | 1078 | New Zealand Women A | female | 3 | token subset |
| 1078 | New Zealand Women A | female | 149 | New Zealand Women | female | 53 | token subset |
| 456 | New Zealand Women U19 | female | 149 | New Zealand Women | female | 53 | token subset |
| 1221 | Nigeria Women | female | 455 | Nigeria Women U19 | female | 10 | token subset |
| 455 | Nigeria Women U19 | female | 1221 | Nigeria Women | female | 9 | token subset |
| 665 | North Delhi Strikers Women | female | 766 | Delhi Womens | female | 6 | token subset |
| 808 | North East Zone Women | female | 810 | North Zone Women | female | 6 | token subset |
| 808 | North East Zone Women | female | 813 | East Zone Women | female | 5 | token subset |
| 810 | North Zone Women | female | 808 | North East Zone Women | female | 5 | token subset |
| 923 | Pakistan A Women  | female | 135 | Pakistan Women | female | 53 | token subset |
| 135 | Pakistan Women | female | 452 | Pakistan Women U19 | female | 8 | token subset |
| 135 | Pakistan Women | female | 923 | Pakistan A Women  | female | 4 | token subset |
| 452 | Pakistan Women U19 | female | 135 | Pakistan Women | female | 53 | token subset |
| 715 | Samoa Women | female | 454 | Samoa Women U19 | female | 8 | token subset |
| 454 | Samoa Women U19 | female | 715 | Samoa Women | female | 5 | token subset |
| 297 | Scotland Women  | female | 459 | Scotland Women U19 | female | 10 | token subset |
| 459 | Scotland Women U19 | female | 297 | Scotland Women  | female | 42 | token subset |
| 1111 | SoBo Mumbai Falcons Women | female | 756 | Mumbai Womens | female | 8 | token subset |
| 136 | South Africa Women | female | 457 | South Africa Women U19 | female | 14 | token subset |
| 457 | South Africa Women U19 | female | 136 | South Africa Women | female | 61 | token subset |
| 664 | South Delhi Superstarz Women | female | 766 | Delhi Womens | female | 6 | token subset |
| 925 | Sri Lanka A Women | female | 42 | Sri Lanka Women | female | 55 | token subset |
| 42 | Sri Lanka Women | female | 446 | Sri Lanka Women U19 | female | 13 | token subset |
| 42 | Sri Lanka Women | female | 925 | Sri Lanka A Women | female | 7 | token subset |
| 446 | Sri Lanka Women U19 | female | 42 | Sri Lanka Women | female | 55 | token subset |
| 522 | The Blaze Women | female | 439 | Wellington Blaze | female | 23 | token subset |
| 301 | United States Of America Women | female | 453 | United States Of America Women U19 | female | 10 | token subset |
| 453 | United States Of America Women U19 | female | 301 | United States Of America Women | female | 28 | token subset |
| 546 | Warriors Women | female | 133 | Guyana Amazon Warriors | female | 24 | token subset |
| 546 | Warriors Women | female | 1195 | India Warriors Women | female | 4 | token subset |
| 439 | Wellington Blaze | female | 522 | The Blaze Women | female | 28 | token subset |
| 148 | West Indies Women | female | 449 | West Indies Women U19 | female | 10 | token subset |
| 449 | West Indies Women U19 | female | 148 | West Indies Women | female | 48 | token subset |
| 1224 | Zimbabwe HPC Women | female | 299 | Zimbabwe Women | female | 22 | token subset |
| 299 | Zimbabwe Women | female | 1224 | Zimbabwe HPC Women | female | 7 | token subset |

### 1d. GUARD — team_id_map merges across genders (must be none; a women's side folded into a men's id, or vice versa)

(none — all 18 remapped ids share the gender of their canonical id)

All duplicate ids remapped (old -> canonical), with match genders:

| old_id | old_name | old_genders | canonical_id | canonical_name | canonical_genders |
|---|---|---|---|---|---|
| 353 | Australian Capital Territory | female | 738 | ACT Meteors Women | female |
| 316 | Barbados Royals | female | 132 | Barbados Royals | female |
| 317 | Guyana Amazon Warriors | female | 133 | Guyana Amazon Warriors | female |
| 1006 | Nepal Women | female | 312 | Nepal Women | female |
| 318 | Trinbago Knight Riders | female | 134 | Trinbago Knight Riders | female |
| 183 | Cambodia | male | 187 | Cambodia | male |
| 496 | Delhi Capitals | male | 39 | Delhi Capitals | male |
| 503 | Gujarat Titans | male | 34 | Gujarat Titans | male |
| 173 | Malaysia | male | 184 | Malaysia | male |
| 189 | Maldives | male | 186 | Maldives | male |
| 495 | Mumbai Indians | male | 33 | Mumbai Indians | male |
| 174 | Papua New Guinea | male | 303 | Papua New Guinea | male |
| 512 | Peshawar Zalmi | male | 280 | Peshawar Zalmi | male |
| 513 | Quetta Gladiators | male | 281 | Quetta Gladiators | male |
| 501 | Rajasthan Royals | male | 41 | Rajasthan Royals | male |
| 498 | Royal Challengers Bengaluru | male | 40 | Royal Challengers Bengaluru | male |
| 486 | Singapore | male | 185 | Singapore | male |
| 502 | Sunrisers Hyderabad | male | 35 | Sunrisers Hyderabad | male |

### 1c. Women's Big Bash / Spring Challenge teams (dedupe status)

| team_id | team_name | team_key | gender | matches | dedupe_status | duplicate_ids_remapped_in |
|---|---|---|---|---|---|---|
| 738 | ACT Meteors Women | c__team__act__514fc | female | 12 | canonical (absorbed duplicates) | 353 |
| 196 | Adelaide Strikers Women | adsw | female | 49 | canonical (single id) |  |
| 193 | Brisbane Heat Women | bhw | female | 55 | canonical (single id) |  |
| 194 | Hobart Hurricanes Women | hbhw | female | 52 | canonical (single id) |  |
| 192 | Melbourne Renegades Women | mlrw | female | 48 | canonical (single id) |  |
| 191 | Melbourne Stars Women | mlsw | female | 48 | canonical (single id) |  |
| 195 | Perth Scorchers Women | perw | female | 53 | canonical (single id) |  |
| 190 | Sydney Sixers Women | sydw | female | 49 | canonical (single id) |  |
| 197 | Sydney Thunder Women | sytw | female | 50 | canonical (single id) |  |

Other women's teams carrying a BBL club word (sanity list; distinct teams unless 1b flags them):

| team_id | team_name | team_key | matches |
|---|---|---|---|
| 665 | North Delhi Strikers Women | a-rz--cricket--ndsw-jeDd | 3 |
| 1193 | Pagariya Strikers Nagpur Women | a-rz--cricket--psnw-jLMK | 3 |

## 2. Venues

- dim_venue rows: 274 before -> 339 now; NEW canonical venues: 65
- venue_id_map: 369 keys, 30 merged into a canonical key (revise_l1)

### 2a. New venues entering L1

| venue_key | venue_name | city | country_code | matches | keys_merged_in |
|---|---|---|---|---|---|
| c__stadium__ukm_ysd_cricket_oval__0cd40 | UKM Cricket Oval | Bangi | MYS | 33 |  |
| c__stadium__judges_field__6c7aa | Judge's Field, Guwahati | Kamrup Metropolitan | IND | 33 |  |
| c__stadium__asian_institute_of_technology_ground__d23af | Asian Institute of Technology (AIT) | Bangkok | THA | 32 |  |
| c__stadium__citipower_centre_junction_oval__d7b85 | CitiPower Centre Junction Oval | St Kilda | AUS | 28 | a-rz--joskm-3qwP,citipod7b85,jjunctic4rv4v |
| a-rz--scgs-j4YV | Sarawak Cricket Ground, Sarawak | Malaysia | MYS | 20 |  |
| a-rz--apalberty7vud5 | Albert Park | Suva | FJI | 20 | a-rz--ap-nZO1 |
| c__stadium__waca_ground__47566 | Western Australian Cricket Association | East Perth | AUS | 19 | c__stadium__western_australian_cricket_association__fbccb,wwaca-gkfmv9z |
| c__stadium__karen_rolton_oval__a9920 | Karen Rolton Oval | Adelaide | AUS | 17 | krkaren-8idgyw |
| a-rz--jcajohor-k0u8xk | Dato' Dr. Harjit Singh Johor Cricket Academy and Oval | Johor Bahru | MYS | 16 |  |
| a-rz--cc-smZq | Cricket Central | Australia | AUS | 14 |  |
| a-rz--mcs-3MTl | Lower Mulpani Cricket Ground | Nepal | NPL | 14 |  |
| c__stadium__drummoyne_oval__fa2ba | Drummoyne Oval | Drummoyne | AUS | 13 |  |
| c__stadium__blacktown_international_sportspark_1__0a6ec | Blacktown International Sportspark | Rooty Hill | AUS | 12 |  |
| a-rz--vbsk-un9T |  Vadodara, BCA Stadium, Kotambi | India | IND | 11 |  |
| c__stadium__nagaland_cricket_association_stadium__d4881 | Nagaland Cricket Association Stadium | Dimapur | IND | 10 |  |
| c__stadium__the_tolerance_oval__61195 | Tolerance Oval | Abu Dhabi | ARE | 10 |  |
| a-rz--gcs-OMlL | Gahanga Cricket Stadium 2, Kigali, Rwanda | Rwanda | RWA | 8 |  |
| c__stadium__kennards_hire_community_oval__74b7e | Kennards Hire Auckland City | Auckland | NZL | 8 |  |
| c__stadium__sydney_olympic_park__7890e | Sydney Olympic Park | Australia | AUS | 7 |  |
| a-rz--scgs-mlu7 | Sovima Cricket Ground, Sovima | India | IND | 6 |  |
| c__stadium__ck_pithawala_cricket_ground_bhimpore__e0dbe | C.K Pithawala Cricket Ground | Surat | IND | 6 |  |
| c__stadium__mahinda_rajapaksa_international_stadium__8600a | Mahinda Rajapaksa International Cricket Stadium | Sooriyawewa | LKA | 6 |  |
| kkensinmkxczk | Kensington Oval | Bridgetown | BRB | 6 |  |
| c__stadium__kole_tunku_jaafar_ground_mantin__751d9 | Kolej Tuanku Ja'afar (KTJ) | Mantin | MYS | 6 |  |
| c__stadium__lady_amritbai_daga_college_ground__259fa | Lady Amritbai Daga College & Smt. Ratnidevi Purohit College | Nagpur | IND | 6 |  |
| c__stadium__university_of_dar_es_salaam__f14cc | University of Dar es Salaam | Tanzania | TZA | 5 |  |
| c__stadium__captain_roop_singh_stadium__ba830 | Captain Roop Singh Cricket Stadium | Gwalior | IND | 5 |  |
| c__stadium__bankstown_oval__61393 | Bankstown Oval | Bankstown | AUS | 5 |  |
| a-rz--pnsm-ARrO | PCA New Stadium, Mullanpur | India | IND | 5 |  |
| c__stadium__lugogo_stadium_kampala__d3d9b | Lugogo Stadium Complex | Kampala | UGA | 5 |  |
| c__stadium__haslegrave_ground__ed1be | Haslegrave Cricket Ground | Loughborough | GBR | 4 |  |
| a-rz--acc-eMTA | Albertslund Cricket Club | Denmark | DNK | 4 |  |
| c__stadium__brabourne_stadium__27ec9 | CCI-Brabourne Stadium | Mumbai City | IND | 4 |  |
| scsydneym0viui | Sydney Cricket Ground | Moore Park | AUS | 3 |  |
| a-rz--igcagn2-5XVp | ICC Global Cricket Academy Ground No 2 | Dubai | ARE | 3 |  |
| a-rz--skc-u7In | SV Kampong Cricket | Utrecht | NLD | 3 |  |
| a-rz--ohcc-gROD | Oak Hill Cricket Club | Ireland | IRL | 3 |  |
| c__stadium__great_barrier_reef_arena__84ab2 | Great Barrier Reef Arena | South Mackay | AUS | 3 | gbragreat-qdj9ed |
| c__stadium__castle_avenue__5f1e2 | Castle Ave | Dublin | IRL | 3 |  |
| c__stadium__three_ws_oval__6ecb2 | 3Ws Oval | Saint Michael | BRB | 3 |  |
| cdchitta2aqy5v | Zahur Ahmed Chowdhury Stadium | Chittagong | BGD | 3 |  |
| bbellerkcprd1 | Blundstone Arena | Bellerive | AUS | 3 |  |
| aauroraz7ljgk | Aurora Stadium Launceston | Launceston | AUS | 2 |  |
| a-rz--mysps-kjaZ | PCA New Cricket Stadium, Ground B, New Chandigarh | India | IND | 2 |  |
| c__stadium__hurstville_oval_hurstville__9862c | Hurstville Oval | Hurstville | AUS | 2 |  |
| a-rz--spsinoviyta3qa | Sinovich St | Pretoria | ZAF | 2 |  |
| a-rz--tnz-0tvb | Tbc, New Zealand | New Zealand | NZL | 2 |  |
| a-rz--mgics-VN2s | MPCA Gwalior International Cricket Stadium | Gwalior | IND | 2 |  |
| a-rz--1rr-30Aa | 1 Raby Rd | Australia | AUS | 1 |  |
| c__stadium__braam_fisherville__6c232 | Bram Fischerville | Soweto | ZAF | 1 |  |
| c__stadium__arundel_castle__aae20 | Arundel Castle Cricket Ground | Northern Ireland | GBR | 1 |  |
| a-rz--sgr-c5EE | St Godwalds Park, Bromsgrove | United Kingdom | GBR | 1 |  |
| a-rz--spspyttygv425t | Spytty Retail Park | United Kingdom | GBR | 1 |  |
| a-rz--rgri-rmDI | RDCA Ground, Raipur, India | India | IND | 1 |  |
| a-rz--cfrgcrickeayikvz | Horsham Sports Club | United Kingdom | GBR | 1 |  |
| a-rz--ccg-cM3X |  Cinch County Ground, Northampton | United Kingdom | GBR | 1 |  |
| a-rz--qpsgqueensur4x3j | Queen's Park | Saint George's | GRD | 1 |  |
| a-rz--fcc-7OIj | Falkland Cricket Club | United Kingdom | GBR | 1 |  |
| a-rz--ccantert6regl | Canterbury Park | Eaglehawk | AUS | 1 |  |
| c__stadium__brunton_memorial_ground__916a2 | Brunton Memorial Ground | Northern Ireland | GBR | 1 |  |
| c__stadium__john_davies_oval__370f4 | John Davies Oval (Cricket Stadium) | Queenstown | NZL | 1 |  |
| c__stadium__kibworth_cricket_club_ground_kibworth__ad5fa | Kibworth Cricket Club | Kibworth | GBR | 1 |  |
| c__stadium__stormont__338be | Stormont | Northern Ireland | GBR | 1 |  |
| c__stadium__steyn_school__d6f06 | Steyn City School | Midrand | ZAF | 1 |  |
| cfncasey-qy1rxu | Casey Fields No 4 | Cranbourne East | AUS | 1 |  |

### 2b. New venue keys merged (by revise_l1) into an existing venue

| old_key | canonical_key | venue_name | city |
|---|---|---|---|
| a-rz--ajarun-jxdsldz | c__stadium__arun_jaitley_stadium__4bba5 | Arun Jaitley Stadium | Delhi |
| a-rz--rcrawalpftdf0v | c__stadium__rawalpindi_cricket_stadium__7fede | Rawalpindi Cricket Stadium | Rawalpindi |
| a-rz--rgirajiv-kvdpk5 | c__stadium__rajiv_gandhi_international_cricket_stadium__e2d74 | Rajiv Gandhi International Cricket Stadium | Hyderabad |
| a-rz--smsawai-lmzcxq | c__stadium__sawai_mansingh_stadium__4c066 | Sawai Mansingh Stadium | Jaipur |
| aballan-uyttai | c__stadium__allan_border_field__5fb24 | Allan Border Field | Albion |
| bbuffal2ipww0 | c__stadium__buffalo_park__e97bc | Buffalo Park | East London |
| blsbrian-mzrl1s | c__stadium__the_brian_lara_cricket_academy__d80f6 | Brian Lara Cricket Academy | San Fernando |
| c__stadium__basin_reserve__c9b84 | c__stadium__cello_basin_reserve__b3001 | Basin Reserve | Wellington |
| c__stadium__edgbaston_stadium__a26bb | a-rz--edgbasgbzq0e | Edgbaston Stadium | Birmingham |
| c__stadium__headingley_cricket_ground__a801e | a-rz--headinv6wlv9 | Headingley Cricket Ground | Headingley |
| c__stadium__mchinnaswamy_stadium__64b76 | c__stadium__m_chinnaswamy_stadium__bfc18 | M. Chinnaswamy Stadium | Bengaluru |
| c__stadium__vidarbha_cricket_association_ground__5b165 | a-rz--vcasvidarb1wfe4o | Vidarbha Cricket Association Stadium | Nagpur |
| c__stadium__wankhede_stadium__dba3b | c__stadium__the_wankhede_stadium__d1df3 | Wankhede Stadium | Mumbai City |
| dsncssdarrenmizzdo | c__stadium__daren_sammy_national_cricket_stadium__aef27 | Daren Sammy National Cricket Stadium | Gros Islet |
| hhagleypshqwi | c__stadium__hagley_oval__d3aba | Hagley Oval | Christchurch |
| jisjsca-iefvoer | c__stadium__jsca_international_stadium_complex__690f7 | JSCA International Stadium Complex | Ranchi |
| mcmelboul4lbq6 | c__stadium__melbourne_cricket_ground__1b031 | Melbourne Cricket Ground | Richmond |
| nsonorth-8aj0qz | c__stadium__north_sydney_oval_no1__d8642 | North Sydney Oval | Sydney |
| pprovidbgazib | c__stadium__providence_stadium__24f4d | Providence Stadium | Georgetown |
| qpqueensmoy5aq | c__stadium__queens_park_oval__801a1 | Queen's Park Oval | Port of Spain |
| sgst-geokc0dz2 | c__stadium__st_georges_park_cricket_ground__62a72 | Saint George's Park | Gqeberha |
| wpawillowvqdeh3 | c__stadium__willowmoore_park__85463 | Sahara Park Willowmoore Cricket Stadium | Benoni |

## 3. Tournaments

- dim_tournament rows: 245 before -> 362 now; NEW: 117; league_keys: 287
- tournament ids in dim_match with NO dim_tournament row (missing from cricket__tournaments; league_key NULL downstream): [1906]
  - 1906: 21 matches, 21 completed, 2026-10-12 .. 2026-10-21, gender=female, e.g. 'Hobart Hurricanes Women vs ACT Meteors Women'

### 3a. New tournaments entering L1

| tournament_id | tournament_name | league_key | gender | start_date | matches | completed | first | last |
|---|---|---|---|---|---|---|---|---|
| 1452 | ACC Women's Asia Cup Rising Stars, 2026 | acc women s asia cup rising stars | female | 2026-02-13 08:00:00 | 15 | 15 | 2026-02-13 | 2026-02-22 |
| 1621 | ACC Women's Premier Cup, 2026 | acc women s premier cup | female | 2026-06-03 07:00:00 | 40 | 40 | 2026-06-03 | 2026-06-13 |
| 1585 | Asian Games Women's T20I Qualifier , 2026 | asian games women s qualifier | female | 2026-05-26 07:00:00 | 10 | 10 | 2026-05-26 | 2026-05-31 |
| 507 | Australia Women tour of Bangladesh,2024 | australia women tour of bangladesh | female | 2024-03-31 11:30:00 | 3 | 3 | 2024-03-31 | 2024-04-04 |
| 396 | Australia Women tour of India, 2023-24 | australia women tour of india | female | 2024-01-05 19:00:00 | 3 | 3 | 2024-01-05 | 2024-01-09 |
| 875 | Australia Women tour of New Zealand, 2025 | australia women tour of new zealand | female | 2025-03-21 07:15:00 | 3 | 3 | 2025-03-21 | 2025-03-26 |
| 1475 | Australia Women tour of West Indies, 2026 | australia women tour of west indies | female | 2026-03-20 04:00:00 | 3 | 3 | 2026-03-20 | 2026-03-24 |
| 375 | Bangladesh Women tour of South Africa, 2023 | bangladesh women tour of south africa | female | 2023-12-03 17:30:00 | 3 | 3 | 2023-12-03 | 2023-12-08 |
| 113 | Bangladesh Women tour of SriLanka Women, 2023 | bangladesh women tour of srilanka women | female | 2023-04-29 09:30:00 | 3 | 3 | 2023-05-09 | 2023-05-12 |
| 904 | Bangladesh Women tour of West Indies, 2025 | bangladesh women tour of west indies | female | 2025-01-28 03:30:00 | 3 | 3 | 2025-01-28 | 2025-02-01 |
| 1429 | Bhutan Women's T20I Tri-Series 2026 | bhutan women s tri series | female | 2026-01-20 10:00:00 | 8 | 8 | 2026-01-20 | 2026-01-29 |
| 1337 | Canada Women tour of Tanzania, 2025 | canada women tour of tanzania | female | 2025-11-04 15:30:00 | 5 | 5 | 2025-11-04 | 2025-11-09 |
| 1324 | Canada Women tour of Uganda, 2025 | canada women tour of uganda | female | 2025-10-20 12:30:00 | 5 | 5 | 2025-10-20 | 2025-10-26 |
| 1558 | Cricket Ireland Women's Super T20 Series  , 2026 | cricket ireland women s super series | female | 2026-05-10 15:15:00 | 6 | 6 | 2026-05-10 | 2026-05-25 |
| 1306 | CSA Women Pro20 Series, 2025/26 | csa women pro series | female | 2025-10-05 13:30:00 | 31 | 31 | 2025-10-05 | 2026-03-13 |
| 1420 | CWI T20 Blaze, 2026 | cwi blaze | female | 2026-01-13 19:00:00 | 18 | 18 | 2026-01-13 | 2026-01-24 |
| 1229 | Delhi Women's Premier League, 2025 | delhi women s premier league | female | 2025-08-17 14:00:00 | 7 | 7 | 2025-08-17 | 2025-08-24 |
| 1448 | Denmark Women tour of Oman 2026 | denmark women tour of oman | female | 2026-02-03 20:00:00 | 4 | 4 | 2026-02-03 | 2026-02-07 |
| 376 | England Women tour of India, 2023 | england women tour of india | female | 2023-12-06 19:00:00 | 3 | 3 | 2023-12-06 | 2023-12-10 |
| 655 | England Women tour of Ireland, T20, 2024 | england women tour of ireland | female | 2024-09-14 19:15:00 | 3 | 2 | 2024-09-14 | 2024-09-17 |
| 731 | England Women tour of South Africa, 2024  | england women tour of south africa | female | 2024-11-24 17:30:00 | 3 | 3 | 2024-11-24 | 2024-11-30 |
| 465 | England Womens Tour Of New Zealand, 2024 | england womens tour of new zealand | female | 2024-03-19 05:30:00 | 5 | 5 | 2024-03-19 | 2024-03-29 |
| 1403 | GCC Womens T20I Championship, 2025 | gcc womens championship | female | 2025-12-12 11:00:00 | 16 | 16 | 2025-12-12 | 2025-12-19 |
| 1043 | GTC Womens Summer Challenge T20 Trophy, 2025 | gtc womens summer challenge trophy | female | 2025-05-04 09:15:00 | 33 | 33 | 2025-05-04 | 2025-05-20 |
| 619 | Hong Kong Women tour of Netherlands, 2024 | hong kong women tour of netherlands | female | 2024-06-17 17:30:00 | 4 | 4 | 2024-06-17 | 2024-06-19 |
| 912 | ICC Under 19 Womens T20 World Cup, 2025 | icc under womens world cup | female | 2025-01-18 08:00:00 | 42 | 41 | 2025-01-18 | 2025-02-02 |
| 1365 | ICC Women's Emerging Nations Trophy, 2025 | icc women s emerging nations trophy | female | 2025-11-20 07:30:00 | 28 | 28 | 2025-11-20 | 2025-11-30 |
| 911 | ICC Women's Under 19 T20 World Cup, 2025 | icc women s under world cup | female | 2025-01-18 08:00:00 | 41 | 41 | 2025-01-18 | 2025-02-02 |
| 1059 | ICC T20 Women's World Cup Asia Qualifier, 2025 | icc women s world cup asia qualifier | female | 2025-05-09 07:30:00 | 21 | 21 | 2025-05-09 | 2025-05-20 |
| 551 | ICC Women's T20 World Cup Qualifier, 2024 | icc women s world cup qualifier | female | 2024-04-25 16:30:00 | 23 | 23 | 2024-04-25 | 2024-05-07 |
| 1426 | ICC Women's T20 World Cup Qualifier, 2026 | icc women s world cup qualifier | female | 2026-01-18 08:45:00 | 29 | 29 | 2026-01-18 | 2026-02-01 |
| 1525 | ICC Womens T20I Challenge Trophy, 2026 | icc womens challenge trophy | female | 2026-04-18 12:30:00 | 20 | 20 | 2026-04-18 | 2026-05-01 |
| 712 | ICC Womens T20 World Cup, 2024 | icc womens world cup | female | 2024-10-03 15:30:00 | 23 | 23 | 2024-10-03 | 2024-10-20 |
| 1541 | ICC Womens T20 World Cup, 2026 | icc womens world cup | female | 2026-06-12 23:00:00 | 33 | 33 | 2026-06-12 | 2026-07-05 |
| 1262 | ICC Womens T20 World Cup East Asia Pacific Qualifier, 2025 | icc womens world cup east asia pacific qualifier | female | 2025-09-09 03:00:00 | 20 | 20 | 2025-09-09 | 2025-09-15 |
| 759 | ICC Womens T20 World Cup Warm-up Matches, 2024 | icc womens world cup warm up matches | female | 2024-09-28 19:30:00 | 10 | 10 | 2024-09-28 | 2024-10-01 |
| 1620 | ICC Womens T20 World Cup Warm-up Matches, 2026 | icc womens world cup warm up matches | female | 2026-06-06 14:30:00 | 12 | 12 | 2026-06-06 | 2026-06-10 |
| 1651 | India A Women tour of England 2026 | india a women tour of england | female | 2026-06-20 19:00:00 | 3 | 3 | 2026-06-20 | 2026-06-25 |
| 1414 | India Women tour of Australia, 2026 | india women tour of australia | female | 2026-02-15 13:45:00 | 3 | 3 | 2026-02-15 | 2026-02-21 |
| 549 | India Women tour of Bangladesh, T20, 2024 | india women tour of bangladesh | female | 2024-04-28 15:30:00 | 5 | 5 | 2024-04-28 | 2024-05-09 |
| 986 | India Women tour of England, T20, 2025 | india women tour of england | female | 2025-06-28 19:00:00 | 5 | 5 | 2025-06-28 | 2025-07-12 |
| 1507 | India Women tour of England, 2026 | india women tour of england | female | 2026-05-28 23:00:00 | 3 | 3 | 2026-05-28 | 2026-06-02 |
| 1473 | India Women tour of South Africa, 2026 | india women tour of south africa | female | 2026-04-17 21:30:00 | 5 | 5 | 2026-04-17 | 2026-04-27 |
| 1154 | Indonesia Women tour of Singapore, 2025 | indonesia women tour of singapore | female | 2025-07-02 07:00:00 | 3 | 3 | 2025-07-02 | 2025-07-05 |
| 818 | Ireland women tour of Bangladesh, T20, 2024 | ireland women tour of bangladesh | female | 2024-12-05 13:30:00 | 3 | 3 | 2024-12-05 | 2024-12-09 |
| 1342 | Ireland Women tour of South Africa 2025 | ireland women tour of south africa | female | 2025-12-05 17:30:00 | 3 | 3 | 2025-12-05 | 2025-12-10 |
| 1636 | Kwibuka Women's T20I Tournament, 2026 | kwibuka women s tournament | female | 2026-06-10 13:15:00 | 20 | 20 | 2026-06-10 | 2026-06-20 |
| 1625 | Madhya Pradesh League T20 Women's, 2026 | madhya pradesh league women s | female | 2026-06-04 09:30:00 | 12 | 4 | 2026-06-04 | 2026-06-13 |
| 1373 | Myanmar Women tour of Singapore, 2025 | myanmar women tour of singapore | female | 2025-11-27 11:30:00 | 4 | 4 | 2025-11-27 | 2025-12-02 |
| 927 | Nepal Womens T20I Tri-Series, 2025 | nepal womens tri series | female | 2025-01-30 12:00:00 | 9 | 9 | 2025-01-30 | 2025-02-07 |
| 223 | Netherlands Women vs Ireland Women, 2023 | netherlands women vs ireland women | female | 2023-08-14 15:30:00 | 3 | 3 | 2023-08-14 | 2023-08-17 |
| 1576 | New Zealand Women’s A tour of Sri Lanka, 2026 | new zealand women s a tour of sri lanka | female | 2026-05-21 10:00:00 | 3 | 3 | 2026-05-21 | 2026-05-25 |
| 658 | New Zealand Women Tour Of Australia, 2024 | new zealand women tour of australia | female | 2024-09-19 14:40:00 | 3 | 3 | 2024-09-19 | 2024-09-24 |
| 494 | New Zealand Women Tour Of England, 2024 | new zealand women tour of england | female | 2024-07-06 19:00:00 | 5 | 5 | 2024-07-06 | 2024-07-17 |
| 1505 | New Zealand Women tour of England, 2026 | new zealand women tour of england | female | 2026-05-20 23:00:00 | 3 | 3 | 2026-05-20 | 2026-05-25 |
| 271 | New Zealand Women tour of South Africa, 2023 | new zealand women tour of south africa | female | 2023-09-24 13:30:00 | 5 | 3 | 2023-10-06 | 2023-10-15 |
| 560 | Pakistan Women tour of England, 2024 | pakistan women tour of england | female | 2024-05-11 19:00:00 | 3 | 3 | 2024-05-11 | 2024-05-19 |
| 1122 | Pakistan Women tour of Ireland, 2025 | pakistan women tour of ireland | female | 2025-08-06 20:30:00 | 3 | 3 | 2025-08-06 | 2025-08-10 |
| 340 | Pakistan Women tour of New Zealand, T20I, 2023 | pakistan women tour of new zealand | female | 2023-12-03 05:30:00 | 3 | 3 | 2023-12-03 | 2023-12-09 |
| 1413 | Pakistan Women tour of South Africa, 2026 | pakistan women tour of south africa | female | 2026-02-10 21:30:00 | 3 | 3 | 2026-02-10 | 2026-02-16 |
| 1653 | Pakistan Women tour of Sri Lanka, 2026 | pakistan women tour of sri lanka | female | 2026-07-31 10:00:00 | 3 | 0 | 2026-07-31 | 2026-08-04 |
| 319 | Pakistan Womens tour of Bangladesh, T20, 2023 | pakistan womens tour of bangladesh | female | 2023-10-25 16:00:00 | 3 | 3 | 2023-10-25 | 2023-10-29 |
| 1517 | Scotland Women's T20I Tri-Series, 2026 | scotland women s tri series | female | 2026-05-28 17:30:00 | 6 | 6 | 2026-05-28 | 2026-06-04 |
| 1405 | SEA Games women's Twenty20 Cricket Competition, 2025 | sea games women s twenty cricket competition | female | 2025-12-15 07:30:00 | 10 | 10 | 2025-12-15 | 2025-12-19 |
| 1341 | Senior Women's Inter Zonal T20 Trophy, 2025 | senior women s inter zonal trophy | female | 2025-11-04 11:00:00 | 16 | 16 | 2025-11-04 | 2025-11-14 |
| 1312 | Senior Women's T20 Trophy, 2025 | senior women s trophy | female | 2025-10-08 09:00:00 | 59 | 59 | 2025-10-08 | 2025-10-31 |
| 439 | South Africa Women tour of Australia, T20, 2024 | south africa women tour of australia | female | 2024-01-27 05:15:00 | 3 | 3 | 2024-01-27 | 2024-01-30 |
| 598 | South Africa Women Tour of India, T20, 2024 | south africa women tour of india | female | 2024-07-05 19:00:00 | 3 | 3 | 2024-07-05 | 2024-07-09 |
| 1443 | South Africa Women tour of New Zealand, 2026 | south africa women tour of new zealand | female | 2026-03-15 07:15:00 | 5 | 5 | 2026-03-15 | 2026-03-25 |
| 229 | South Africa Women tour of Pakistan, 2023 | south africa women tour of pakistan | female | 2023-09-01 18:30:00 | 3 | 3 | 2023-09-01 | 2023-09-04 |
| 725 | South Africa Women tour of Pakistan, 2024 | south africa women tour of pakistan | female | 2024-09-16 19:30:00 | 3 | 3 | 2024-09-16 | 2024-09-20 |
| 983 | South Africa Women tour of West Indies, T20, 2025 | south africa women tour of west indies | female | 2025-06-20 23:30:00 | 3 | 3 | 2025-06-20 | 2025-06-23 |
| 776 | T20 Spring Challenge, 2024 | spring challenge | female | 2024-10-11 04:30:00 | 21 | 21 | 2024-10-11 | 2024-10-20 |
| 1325 | T20 Spring Challenge, 2025 | spring challenge | female | 2025-10-21 04:30:00 | 21 | 21 | 2025-10-21 | 2025-10-30 |
| 1498 | Sri Lanka Women tour of Bangladesh 2026 | sri lanka women tour of bangladesh | female | 2026-04-28 13:00:00 | 3 | 3 | 2026-04-28 | 2026-05-02 |
| 250 | Sri Lanka Women tour of England, 2023 | sri lanka women tour of england | female | 2023-08-31 22:30:00 | 3 | 3 | 2023-08-31 | 2023-09-06 |
| 1392 | Sri Lanka Women tour of India 2025 | sri lanka women tour of india | female | 2025-12-21 19:00:00 | 5 | 5 | 2025-12-21 | 2025-12-30 |
| 652 | Sri Lanka Women tour of Ireland, T20, 2024 | sri lanka women tour of ireland | female | 2024-08-11 20:30:00 | 2 | 2 | 2024-08-11 | 2024-08-13 |
| 873 | Sri Lanka Women tour of New Zealand, 2025 | sri lanka women tour of new zealand | female | 2025-03-14 11:45:00 | 3 | 3 | 2025-03-14 | 2025-03-18 |
| 497 | Sri Lanka Women tour of South Africa, T20, 2024 | sri lanka women tour of south africa | female | 2024-03-27 21:30:00 | 3 | 3 | 2024-03-27 | 2024-04-03 |
| 1450 | Sri Lanka Women tour of West Indies 2026 | sri lanka women tour of west indies | female | 2026-02-28 22:30:00 | 3 | 3 | 2026-02-28 | 2026-03-03 |
| 1658 | Sri Lanka Women U19 tour of India 2026 | sri lanka women u tour of india | female | 2026-06-22 13:00:00 | 3 | 3 | 2026-06-22 | 2026-06-27 |
| 1671 | Switzerland Women tour of Denmark, 2026 | switzerland women tour of denmark | female | 2026-06-27 14:30:00 | 4 | 4 | 2026-06-27 | 2026-06-28 |
| 1307 | United Arab Emirates Women tour of Zimbabwe 2025 | united arab emirates women tour of zimbabwe | female | 2025-10-05 17:00:00 | 2 | 2 | 2025-10-05 | 2025-10-06 |
| 1061 | USA Women tour of Netherlands,2025 | usa women tour of netherlands | female | 2025-06-07 15:30:00 | 6 | 6 | 2025-06-07 | 2025-06-13 |
| 1628 | Vidarbha Women's Premier League 2026 | vidarbha women s premier league | female | 2026-06-07 19:30:00 | 8 | 8 | 2026-06-07 | 2026-06-14 |
| 1579 | Vitality Blast Women 2026 | vitality blast women | female | 2026-05-22 18:30:00 | 57 | 54 | 2026-05-22 | 2026-07-17 |
| 1582 | Vitality Blast Women League 2, 2026 | vitality blast women league | female | 2026-05-22 18:45:00 | 38 | 38 | 2026-05-22 | 2026-07-12 |
| 270 | West Indies Women tour of Australia, 2023 | west indies women tour of australia | female | 2023-10-01 06:50:00 | 3 | 3 | 2023-10-01 | 2023-10-05 |
| 913 | West Indies Women tour of England, 2025 | west indies women tour of england | female | 2025-05-21 23:00:00 | 3 | 3 | 2025-05-21 | 2025-05-26 |
| 841 | West Indies Women tour of India, 2024 | west indies women tour of india | female | 2024-12-15 19:00:00 | 3 | 3 | 2024-12-15 | 2024-12-19 |
| 534 | West Indies women tour of Pakistan, 2024 | west indies women tour of pakistan | female | 2024-04-26 20:00:00 | 5 | 5 | 2024-04-26 | 2024-05-03 |
| 596 | West Indies Women tour of Sri Lanka, 2024 | west indies women tour of sri lanka | female | 2024-06-24 10:00:00 | 3 | 3 | 2024-06-24 | 2024-06-28 |
| 675 | Women's Caribbean Premier League, 2024 | women s caribbean premier league | female | 2024-08-22 04:30:00 | 7 | 7 | 2024-08-22 | 2024-08-30 |
| 1220 | Women's Caribbean Premier League, 2025 | women s caribbean premier league | female | 2025-09-06 23:30:00 | 7 | 7 | 2025-09-06 | 2025-09-17 |
| 1599 | Women’s Mumbai T20 League, 2026 | women s mumbai league | female | 2026-06-02 09:30:00 | 7 | 7 | 2026-06-02 | 2026-06-13 |
| 1099 | Women's T20I Series in Japan, 2025 | women s series in japan | female | 2025-06-03 06:00:00 | 12 | 12 | 2025-06-03 | 2025-06-08 |
| 1522 | Women's Tri-Series in Ireland, 2026 | women s tri series in ireland | female | 2026-05-28 20:30:00 | 6 | 6 | 2026-05-28 | 2026-06-04 |
| 1093 | Women's Vitality Blast T20, 2025 | women s vitality blast | female | 2025-05-30 19:00:00 | 59 | 59 | 2025-05-30 | 2025-07-27 |
| 129 | Womens Ashes 2023 | womens ashes | female | 2023-06-22 15:30:00 | 3 | 3 | 2023-07-01 | 2023-07-08 |
| 824 | Womens Ashes, 2025 | womens ashes | female | 2025-01-20 13:45:00 | 3 | 3 | 2025-01-20 | 2025-01-25 |
| 632 | Womens Asia Cup, 2024 | womens asia cup | female | 2024-07-19 14:00:00 | 15 | 15 | 2024-07-19 | 2024-07-28 |
| 309 | Womens Big Bash League, 2023 | womens big bash league | female | 2023-10-19 14:10:00 | 59 | 59 | 2023-10-19 | 2023-12-02 |
| 765 | Womens Big Bash League, 2024 | womens big bash league | female | 2024-10-27 08:10:00 | 43 | 43 | 2024-10-27 | 2024-12-01 |
| 1316 | Womens Big Bash League, 2025 | womens big bash league | female | 2025-11-09 08:10:00 | 43 | 43 | 2025-11-09 | 2025-12-13 |
| 227 | Womens Caribbean Premier League 2023 | womens caribbean premier league | female | 2023-09-01 00:30:00 | 21 | 21 | 2023-09-01 | 2023-09-11 |
| 453 | Womens Premier League, 2024 | womens premier league | female | 2024-02-23 20:00:00 | 22 | 22 | 2024-02-23 | 2024-03-17 |
| 918 | Womens Premier League, 2025 | womens premier league | female | 2025-02-14 19:30:00 | 22 | 22 | 2025-02-14 | 2025-03-15 |
| 1400 | Womens Premier League, 2026 | womens premier league | female | 2026-01-09 19:30:00 | 22 | 22 | 2026-01-09 | 2026-02-05 |
| 1354 | Womens T20I Quadrangular Series in Thailand 2025 | womens quadrangular series in thailand | female | 2025-11-14 07:30:00 | 6 | 6 | 2025-11-14 | 2025-11-17 |
| 880 | Womens Super Smash, 2024-25 | womens super smash | female | 2024-12-26 06:40:00 | 32 | 32 | 2024-12-26 | 2025-02-02 |
| 1407 | Womens Super Smash, 2025-26 | womens super smash | female | 2025-12-26 10:50:00 | 32 | 32 | 2025-12-26 | 2026-01-31 |
| 671 | Womens Tri-Series in Netherlands, T20, 2024 | womens tri series in netherlands | female | 2024-08-14 17:30:00 | 3 | 3 | 2024-08-14 | 2024-08-16 |
| 1120 | Zimbabwe Women tour of Ireland, 2025 | zimbabwe women tour of ireland | female | 2025-07-20 20:30:00 | 3 | 3 | 2025-07-20 | 2025-07-23 |
| 1416 | Zimbabwe Women tour of New Zealand, 2026 | zimbabwe women tour of new zealand | female | 2026-02-25 11:45:00 | 3 | 3 | 2026-02-25 | 2026-03-01 |
| 1527 | Zimbabwe Women tour of Pakistan 2026 | zimbabwe women tour of pakistan | female | 2026-05-12 20:00:00 | 3 | 3 | 2026-05-12 | 2026-05-15 |
| 1025 | Zimbabwe Women tour of USA, 2025 | zimbabwe women tour of usa | female | 2025-04-25 21:15:00 | 3 | 3 | 2025-04-25 | 2025-04-29 |

### 3b. league_key grouping for the watched leagues

- league_key = `big bash league` (male; 4 tournament id(s), 183 matches)
    - 11  Big Bash League 2022-23  [2022-12-18 .. 2023-02-04]  51 matches, 48 completed
    - 381  Big Bash League, 2023-2024  [2023-12-07 .. 2024-01-24]  44 matches, 44 completed
    - 834  Big Bash League, 2024-25  [2024-12-15 .. 2025-01-27]  44 matches, 44 completed
    - 1356  Big Bash League, 2025-2026  [2025-12-14 .. 2026-01-25]  44 matches, 44 completed
- league_key = `spring challenge` (female; 2 tournament id(s), 42 matches)
    - 776  T20 Spring Challenge, 2024  [2024-10-11 .. 2024-10-20]  21 matches, 21 completed
    - 1325  T20 Spring Challenge, 2025  [2025-10-21 .. 2025-10-30]  21 matches, 21 completed
- league_key = `womens big bash league` (female; 3 tournament id(s), 145 matches)
    - 309  Womens Big Bash League, 2023  [2023-10-19 .. 2023-12-02]  59 matches, 59 completed
    - 765  Womens Big Bash League, 2024  [2024-10-27 .. 2024-12-01]  43 matches, 43 completed
    - 1316  Womens Big Bash League, 2025  [2025-11-09 .. 2025-12-13]  43 matches, 43 completed

### 3c. league_keys shared by BOTH genders (should be none — women's leagues carry 'women' in the name)

(none)
