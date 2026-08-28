# 2026 season positional fantasy rankings, standard/non-PPR scoring,
# sourced from fantasyfootballcalculator.com/rankings/<pos> (fetched live,
# refreshed 2026-08-28). Format per line: "PlayerName - TEAM" in rank order
# (rank = line position). Defense block sourced from
# fantasyfootballcalculator.com/rankings/defense -- all 32 teams ranked this
# time (previously only 7 of 32, see DEF_RANKS_PARTIAL in git history).

QB_RANKS = """
Josh Allen - BUF
Drake Maye - NE
Lamar Jackson - BAL
Joe Burrow - CIN
Dak Prescott - DAL
Jayden Daniels - WAS
Matthew Stafford - LAR
Jalen Hurts - PHI
Brock Purdy - SF
Trevor Lawrence - JAX
Caleb Williams - CHI
Jared Goff - DET
Patrick Mahomes - KC
Justin Herbert - LAC
Bo Nix - DEN
Jaxson Dart - NYG
Baker Mayfield - TB
Tyler Shough - NO
Kyler Murray - MIN
Sam Darnold - SEA
Jordan Love - GB
C.J. Stroud - HOU
Daniel Jones - IND
Bryce Young - CAR
Malik Willis - MIA
Cam Ward - TEN
Aaron Rodgers - PIT
Geno Smith - NYJ
Jacoby Brissett - ARI
Fernando Mendoza - LV
Deshaun Watson - CLE
Tua Tagovailoa - ATL
Michael Penix Jr. - ATL
Shedeur Sanders - CLE
Kirk Cousins - LV
Taylen Green - CLE
J.J. McCarthy - MIN
Spencer Rattler - NO
Mason Rudolph - PIT
Carson Beck - ARI
Marcus Mariota - WAS
Jameis Winston - NYG
Ty Simpson - LAR
Davis Mills - HOU
Tyrod Taylor - GB
Mac Jones - SF
Anthony Richardson Sr. - IND
Joe Milton III - DAL
Justin Fields - KC
Joe Flacco - CIN
Kenny Pickett - CAR
Quinn Ewers - MIA
Gardner Minshew II - ARI
Andy Dalton - PHI
Jake Browning - TB
Cade Klubnik - NYJ
Riley Leonard - IND
Chris Oladokun - KC
Trey Lance - LAC
Will Levis - TEN
Tyler Huntley - BAL
Sam Howell - DAL
Tyson Bagent - CHI
Behren Morton - NE
Adrian Martinez - SF
Garrett Nussmeier - KC
Cole Payton - PHI
Will Howard - PIT
Drew Allar - PIT
Drew Lock - SEA
Kyle Allen - BUF
Nick Mullens - JAX
Shane Buechele - BUF
Mitchell Trubisky - TEN
Jarrett Stidham - DEN
Joshua Dobbs - DET
Tanner McKee - PHI
Tommy DeVito - NE
Jalen Milroe - SEA
Brady Cook - NYJ
Aidan O'Connell - LV
Max Brosmer - MIN
Skylar Thompson - BAL
Hendon Hooker - TEN
Luke Altmyer - DET
Easton Stick - IND
Stetson Bennett IV - LAR
Brandon Allen - NYG
Sam Ehlinger - DEN
Sean Clifford - CIN
Graham Mertz - HOU
Cam Miller - MIA
Josh Johnson - CIN
Case Keenum - CHI
Kurtis Rourke - SF
Athan Kaliakmanis - WAS
Kyle McCord - GB
Jalon Daniels - TB
Bailey Zappe - NYJ
Dillon Gabriel - CLE
Zach Wilson - NO
Sam Hartman - WAS
Jake Haener - NYG
Carson Wentz - MIN
Cooper Rush - ATL
Kyle Trask - CAR
"""

RB_RANKS = """
Jahmyr Gibbs - DET
Bijan Robinson - ATL
Jonathan Taylor - IND
Derrick Henry - BAL
Christian McCaffrey - SF
James Cook III - BUF
De'Von Achane - MIA
Saquon Barkley - PHI
Chase Brown - CIN
Josh Jacobs - GB
Kyren Williams - LAR
Kenneth Walker - KC
Ashton Jeanty - LV
Omarion Hampton - LAC
Javonte Williams - DAL
Jeremiyah Love - ARI
Breece Hall - NYJ
Cam Skattebo - NYG
Travis Etienne Jr. - NO
D'Andre Swift - CHI
Bucky Irving - TB
Bhayshul Tuten - JAX
Quinshon Judkins - CLE
David Montgomery - HOU
TreVeyon Henderson - NE
Rhamondre Stevenson - NE
Tony Pollard - TEN
Jaylen Warren - PIT
J.K. Dobbins - DEN
Jadarian Price - SEA
Rico Dowdle - PIT
Chuba Hubbard - CAR
Jacory Croskey-Merritt - WAS
Kyle Monangai - CHI
Jonathon Brooks - CAR
Jordan Mason - MIN
Blake Corum - LAR
Aaron Jones Sr. - MIN
RJ Harvey - DEN
Kenny Gainwell - TB
Rachaad White - WAS
Zach Charbonnet - SEA
Woody Marks - HOU
Tyjae Spears - TEN
Isiah Pacheco - DET
Chris Rodriguez Jr. - JAX
Tyrone Tracy Jr. - NYG
Alvin Kamara - NO
Tyler Allgeier - ARI
Brian Robinson - ATL
Tank Bigsby - PHI
Justice Hill - BAL
Samaje Perine - CIN
Mike Washington Jr. - LV
Dylan Sampson - CLE
Braelon Allen - NYJ
Ty Johnson - BUF
Malik Davis - DAL
AJ Dillon - CAR
Keaton Mitchell - LAC
Kaelon Black - SF
James Conner - ARI
Jonah Coleman - DEN
Emari Demercado - KC
Jordan James - SF
Kimani Vidal - LAC
MarShawn Lloyd - GB
Jaylen Wright - MIA
Najee Harris - NYG
Ray Davis - BUF
Adam Randall - BAL
Devin Singletary - NYG
Sean Tucker - TB
Jaydon Blue - DAL
Chris Brooks - GB
Emanuel Wilson - SEA
Emmett Johnson - KC
Isaiah Davis - NYJ
Jawhar Jordan - HOU
Brashard Smith - KC
George Holani - SEA
Kyle Juszczyk - SF
Ollie Gordon II - MIA
Devin Neal - NO
Jeremy McNichols - WAS
LeQuint Allen Jr. - JAX
J'Mari Taylor - JAX
Raheim Sanders - CLE
DJ Giddens - IND
Brittain Brown - CHI
Jam Miller - NE
Salvon Ahmed - CHI
Roschon Johnson - CHI
Frank Gore Jr. - BUF
Deuce Vaughn - HOU
Isaac Guerendo - SF
Carlos Washington Jr. - MIA
Phil Mafah - DAL
Kaytron Allen - WAS
Kendre Miller - NO
Seth McGowan - IND
Trayveon Williams - DET
Will Shipley - PHI
Hunter Luepke - DAL
Demond Claiborne - MIN
Connor Heyward - LV
Dameon Pierce - PHI
Jaret Patterson - LAC
Nathan Carter - ATL
Riley Nowakowski - PIT
Tahj Brooks - CIN
Zavier Scott - MIN
Andrew Beck - NYJ
Donovan Edwards - MIA
Nicholas Singleton - TEN
Eli Heidenreich - PIT
Trevor Etienne - CAR
Rasheen Ali - BAL
Michael Burton - CLE
Kaleb Johnson - PIT
Jaydn Ott - KC
Ameer Abdullah - JAX
Jamal Haynes - CIN
Adam Prentice - DEN
Dean Connors - LAR
Alec Ingold - LAC
Damien Martinez - GB
Max Bredeson - MIN
British Brooks - HOU
Reggie Gilliam - NE
"""

WR_RANKS = """
Puka Nacua - LAR
Ja'Marr Chase - CIN
Jaxon Smith-Njigba - SEA
Amon-Ra St. Brown - DET
Drake London - ATL
CeeDee Lamb - DAL
Rashee Rice - KC
Justin Jefferson - MIN
George Pickens - DAL
A.J. Brown - NE
Nico Collins - HOU
Chris Olave - NO
Zay Flowers - BAL
Malik Nabers - NYG
Tetairoa McMillan - CAR
Jameson Williams - DET
Tee Higgins - CIN
Emeka Egbuka - TB
Davante Adams - LAR
Garrett Wilson - NYJ
DeVonta Smith - PHI
Terry McLaurin - WAS
Rome Odunze - CHI
Ladd McConkey - LAC
DJ Moore - BUF
Christian Watson - GB
Alec Pierce - IND
Mike Evans - SF
Jaylen Waddle - DEN
Courtland Sutton - DEN
DK Metcalf - PIT
Luther Burden III - CHI
Marvin Harrison Jr. - ARI
Parker Washington - JAX
Brian Thomas Jr. - JAX
Carnell Tate - TEN
Michael Wilson - ARI
Quentin Johnston - LAC
Chris Godwin Jr. - TB
Jordan Addison - MIN
Jakobi Meyers - JAX
Jayden Reed - GB
Xavier Worthy - KC
Michael Pittman Jr. - PIT
Deebo Samuel Sr. - SF
Romeo Doubs - NE
Matthew Golden - GB
Stefon Diggs - WAS
Josh Downs - IND
Wan'Dale Robinson - TEN
Makai Lemon - PHI
Rashid Shaheed - SEA
Khalil Shakir - BUF
Jalen Coker - CAR
Jerry Jeudy - CLE
KC Concepcion - CLE
Tre Tucker - LV
Rashod Bateman - BAL
Jalen McMillan - TB
Calvin Ridley - TEN
De'Zhaun Stribling - SF
Jauan Jennings - MIN
Denzel Boston - CLE
Keenan Allen - IND
Jalen Nailor - LV
Malik Washington - MIA
Cooper Kupp - SEA
Tank Dell - HOU
Adonai Mitchell - NYJ
Bub Means - NO
Devaughn Vele - NO
Jordyn Tyson - NO
Kayshon Boutte - HOU
Darius Slayton - NYG
Ja'Kobi Lane - BAL
Travis Hunter - JAX
Tyquan Thornton - KC
Ryan Flournoy - DAL
Xavier Hutchinson - HOU
Jaylin Noel - HOU
Troy Franklin - DEN
Isaac TeSlaa - DET
Germie Bernard - PIT
Xavier Legette - CAR
Caleb Douglas - MIA
Dontayvion Wicks - PHI
Tre' Harris - LAC
Antonio Williams - WAS
Tory Horton - SEA
Jalen Tolbert - MIA
Omar Cooper Jr. - NYJ
Andrei Iosivas - CIN
Malik Benson - LV
Elic Ayomanor - TEN
Keon Coleman - BUF
KaVontae Turpin - DAL
Pat Bryant - DEN
Chimere Dike - TEN
Chris Bell - MIA
Ted Hurst III - TB
Marvin Mims Jr. - DEN
Jahan Dotson - ATL
DeMario Douglas - NE
Christian Kirk - SF
Brandon Aiyuk - SF
Darnell Mooney - NYG
Ashton Dulin - IND
Jack Bech - LV
Joshua Palmer - BUF
Demarcus Robinson - SF
Hollywood Brown - PHI
Luke McCaffrey - WAS
Cedric Tillman - FA
Kendrick Bourne - ARI
Zachariah Branch - ATL
Kalif Raymond - CHI
Savion Williams - GB
Mack Hollins - NE
Dyami Brown - WAS
Malachi Fields - NYG
Tutu Atwell - LAR
Jahdae Walker - CHI
Devontez Walker - BAL
Calvin Austin III - NYG
Olamide Zaccheaus - ATL
Cyrus Allen - KC
Zavion Thomas - CHI
Isaiah Williams - NYJ
Isaiah Bond - CLE
Treylon Burks - WAS
"""

TE_RANKS = """
Trey McBride - ARI
Brock Bowers - LV
Colston Loveland - CHI
Tyler Warren - IND
Dallas Goedert - PHI
Harold Fannin Jr. - CLE
Tucker Kraft - GB
Mark Andrews - BAL
George Kittle - SF
Kyle Pitts Sr. - ATL
Sam LaPorta - DET
Travis Kelce - KC
Isaiah Likely - NYG
Dalton Kincaid - BUF
Hunter Henry - NE
Jake Ferguson - DAL
Juwan Johnson - NO
Brenton Strange - JAX
Dalton Schultz - HOU
Pat Freiermuth - PIT
AJ Barner - SEA
Greg Dulcich - MIA
Kenyon Sadiq - NYJ
T.J. Hockenson - MIN
Chig Okonkwo - WAS
Cade Otton - TB
Terrance Ferguson - LAR
Oronde Gadsden - LAC
Colby Parkinson - LAR
David Njoku - LAC
Mike Gesicki - CIN
Darren Waller - CAR
Gunnar Helm - TEN
Evan Engram - DEN
Mason Taylor - NYJ
Dawson Knox - BUF
Theo Johnson - NYG
Michael Mayer - LV
Tyler Higbee - LAR
Jake Tonges - SF
Cole Kmet - CHI
Darnell Washington - PIT
Noah Fant - NO
Josh Oliver - MIN
Tommy Tremble - CAR
Noah Gray - KC
Elijah Arroyo - SEA
Charlie Kolar - LAC
Austin Hooper - ATL
Erick All Jr. - CIN
Daniel Bellinger - TEN
Brock Wright - DET
Will Kacmarek - MIA
Eli Raridon - NE
Adam Trautman - DEN
Eli Stowers - PHI
Luke Musgrave - GB
Elijah Higgins - ARI
Davis Allen - LAR
Ja'Tavion Sanders - CAR
Nate Boerkircher - JAX
Mitchell Evans - CAR
Drew Sample - CIN
Jackson Hawes - BUF
John Bates - WAS
Nick Vannett - SEA
Jeremy Ruckert - NYJ
Grant Calcaterra - PHI
Ben Sinnott - WAS
Ben Sims - MIA
Michael Trigg - DAL
Cade Stover - HOU
Marlin Klein - HOU
Zack Kuntz - DAL
Luke Schoonmaker - DAL
Jack Endries - CIN
Hayden Rucci - SF
Tanner Hudson - CIN
John Michael Gyllenborg - KC
Tanner Conner - NYG
Foster Moreau - HOU
Mo Alie-Cox - IND
Cam Grandy - CIN
Jaheim Bell - PIT
Seydou Traore - MIA
Nate Adkins - DEN
Durham Smythe - BAL
Payne Durham - TB
Hunter Long - JAX
Charlie Woerner - ATL
Devin Culp - TB
Will Mallory - IND
Brevyn Spann-Ford - DAL
Keleki Latu - BUF
Oscar Delp - NO
Luke Farrell - SF
Blake Whiteheart - CLE
Dallen Bentley - DEN
Drake Dabney - GB
Max Klare - LAR
Drew Ogletree - IND
James Mitchell - CAR
Josh Whyle - GB
Tyler Conklin - DET
Tanner Koziol - JAX
Sam Roush - CHI
Ian Thomas - LV
Justin Joly - DEN
Matt Hibner - BAL
Jared Wiley - KC
Lucas Krull - DEN
Tip Reiman - ARI
Josh Cuevas - BAL
Joe Royer - CLE
Chris Manhertz - NYG
CJ Dippre - NE
Ko Kieft - TB
Eric Saubert - SEA
Johnny Mundt - PHI
Moliki Matavao - NO
Cameron Latu - PHI
Shane Zylstra - BUF
Jelani Woods - NYJ
Stone Smartt - PHI
Teagan Quitoriano - ARI
Jack Stoll - CLE
Zaire Mitchell-Paden - NO
Ben Yurosek - MIN
Nikola Kalinic - CHI
Kylen Granson - TEN
"""

K_RANKS = """
Brandon Aubrey - DAL
Jason Myers - SEA
Ka'imi Fairbairn - HOU
Cameron Dicker - LAC
Jake Bates - DET
Harrison Mevis - LAR
Chase McLaughlin - TB
Tyler Loop - BAL
Cam Little - JAX
Blake Grupe - IND
Wil Lutz - DEN
Will Reichard - MIN
Harrison Butker - KC
Cairo Santos - CHI
Eddy Piñeiro - SF
Evan McPherson - CIN
Andy Borregales - NE
Jake Elliott - PHI
Tyler Bass - BUF
Chris Boswell - PIT
Trey Smack - GB
Charlie Smyth - NO
Nick Folk - ATL
Chad Ryland - ARI
Drew Stevens - WAS
Joey Slye - TEN
Riley Patterson - MIA
Ryan Fitzgerald - CAR
Jason Sanders - NYJ
Matt Gay - LV
Andre Szmyt - CLE
Ben Sauls - NYG
Daniel Carlson - NO
Dominic Zvada - NYG
Spencer Shrader - IND
Tanner Brown - NO
"""

# All 32 NFL defenses, ranked (previously only 7 of 32 had a rank -- fixed
# 2026-08-24 by fetching the full defense rankings page).
DEF_RANKS = """
Seattle Seahawks
Denver Broncos
Houston Texans
Minnesota Vikings
Los Angeles Rams
Detroit Lions
Pittsburgh Steelers
New England Patriots
Los Angeles Chargers
Philadelphia Eagles
Atlanta Falcons
Cleveland Browns
Jacksonville Jaguars
Buffalo Bills
Tennessee Titans
New Orleans Saints
Cincinnati Bengals
Baltimore Ravens
Washington Commanders
Chicago Bears
New York Giants
Miami Dolphins
New York Jets
Tampa Bay Buccaneers
Indianapolis Colts
Dallas Cowboys
Kansas City Chiefs
Green Bay Packers
Las Vegas Raiders
Carolina Panthers
Arizona Cardinals
San Francisco 49ers
"""

TEAM_ABBR2 = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

ALL_32_DEFENSES2 = sorted(TEAM_ABBR2.values())
