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
Jack Strand - ATL
Joe Fagnano - BAL
Austin Reed - BAL
Haynes King - CAR
Miller Moss - CHI
Kedon Slovis - ARI
Brett Rypien - HOU
Carter Bradley - JAX
Joey Aguilar - JAX
Jacob Clark - LV
DJ Uiagalelei - LAC
Matthew Caldwell - LAR
Mark Gronowski - MIA
Hunter Dekkers - NO
Connor Bazelak - TB
"""

# The following 15 entries were added 2026-08-30 during the same active-
# roster completeness pass as the WR list (see WR_RANKS below) -- camp-
# battle winners and depth arms a fantasy-relevant source naturally skips.
# Sequential ranks here (QB107+) are not a scouted order, just "comes
# after the real rankings."
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
Trey Benson - ARI
Evan Hull - ARI
Corey Kiner - ARI
Bam Knight - ARI
Tre Stewart - ARI
Tyler Goodson - ATL
Cash Jones - ATL
Trey Sermon - ATL
Dontae McMillan - BAL
Elijah Tau-Tolliver - BAL
Jonathan Ward - BAL
Jackson Acker - BUF
Ben VanSumeren - BUF
Ian Wheeler - BUF
Miles Davis - CAR
Anthony Tyus III - CAR
Gary Brightwell - CIN
Kentrel Bullock - CIN
Kendall Milton - CIN
Davon Booth - CLE
Ahmani Marshall - CLE
Israel Abanikanda - DAL
Jashaun Corbin - DAL
Tyler Badie - DEN
Jaleel McLaughlin - DEN
Cody Schrader - DEN
Jacob Saylors - DET
Jabari Small - DET
Sione Vaki - DET
Roydell Williams - DET
Pierre Strong Jr. - GB
Jaden Nixon - GB
Derek Parish - HOU
Noah Whittington - HOU
Owen Wright - HOU
Ulysses Bentley IV - IND
Anderson Castle - IND
DeeJay Dallas - JAX
EJ Smith - KC
Dylan Laube - LV
Dare Ogunbowale - LV
Roman Hemby - LV
Gregory Desrosiers Jr. - LAC
Amar Johnson - LAC
Ronnie Rivers - LAR
Jordan Waters - LAR
Coleman Bennett - MIA
DJ Herman - MIA
Jarquez Hunter - MIA
Jermar Jefferson - MIN
Hassan Haskins - NE
JaMycal Hasty - NE
Lan Larison - NE
Ty Chandler - NO
CJ Donaldson - NO
Audric Estime - NO
Zamir White - NO
Damon Bankston - NYG
Eric Gray - NYG
Grant Finley - NYG
Kene Nwangwu - NYJ
Dominic Richardson - NYJ
Chip Trayanum - NYJ
Jordan Mims - PHI
Carson Steele - PHI
Max Hurleman - PIT
Lew Nichols III - PIT
Alex Tecza - PIT
Khalil Herbert - SF
Sincere McCormick - SF
Justin Jones - SEA
Jacardia Wright - SEA
Brock Lampe - SEA
Brady Russell - SEA
Josh Williams - TB
Barika Kpeenu - TB
Michael Carter - TEN
Julius Chestnut - TEN
D'Ernest Johnson - TEN
Kalel Mullings - TEN
Robert Henry Jr. - WAS
Craig Reynolds - WAS
"""

# The following 82 entries were added 2026-08-30 during the same active-
# roster completeness pass as the WR list below -- camp-battle winners,
# UDFA depth, and trade/waiver pickups a fantasy-relevant source naturally
# skips. Sequential ranks here (RB131+) are not a scouted order, just
# "comes after the real rankings."
# The final 237 entries (after "Treylon Burks - WAS") were added 2026-08-29,
# mid-draft-day, extending WR coverage beyond fantasyfootballcalculator.com's
# fantasy-relevant top-130 to every rosterable WR across all 32 teams
# (rookies, camp-body depth, recent trades/signings). Added at Jon's request
# after he noticed Barion Brown (NO, a 2026 6th-round rookie) was missing.
# Sourced via web research (team roster pages), not ADP -- these get
# sequential ranks (WR131+) purely as a side effect of parse_ranked_block()'s
# enumerate(); that is NOT a scouted/ordered rank, just "comes after the real
# rankings." Don't be surprised these ranks don't mean anything meaningful.
#
# One deliberate exception to "active roster only": Tyreek Hill (added to
# the very end of this block, 2026-08-30) is a free agent as of this
# writing, unsigned while recovering from injury -- not on any team. Jon
# asked for him specifically despite that, since he's a real player worth
# tracking/watchlisting for a keeper league even without a current team.
# His nflTeam is the literal string "Free Agent" (not a TEAM_ABBR2 code) so
# it displays as-is and correctly produces no bye-week badge.
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
Jalen Brooks - ARI
Devin Duvernay - ARI
Simi Fehoko - ARI
Ihmir Smith-Marsette - ARI
Reggie Virgil - ARI
Harrison Wallace III - ARI
Vinny Anthony II - ATL
Beaux Collins - ATL
Dylan Drummond - ATL
Keelan Marion - ATL
Antwane Wells Jr. - ATL
Xavier Guillory - BAL
Cornelius Johnson - BAL
Chris Moore - BAL
Elijah Sarratt - BAL
Octavian Smith - BAL
Dayton Wade - BAL
LaJohntay Wester - BAL
Skyler Bell - BUF
Stephen Gosnell - BUF
Mecole Hardman - BUF
Ja'Mori Maclin - BUF
Dante Pettis - BUF
Trent Sherfield - BUF
Quentin Skinner - BUF
Max Tomczak - BUF
Elijah Cooks - CAR
Jimmy Horn Jr. - CAR
John Metchie III - CAR
David Moore - CAR
Ja'Seem Reed - CAR
Brycen Tremayne - CAR
Casey Washington - CAR
Maurice Alexander - CHI
Kaden Davis - CHI
Omari Kelly - CHI
Ray-Ray McCloud - CHI
Scott Miller - CHI
JP Richardson - CHI
Xavier Johnson - CIN
Charlie Jones - CIN
Dohnte Meyers - CIN
Jordan Moore - CIN
Kendric Pryor - CIN
Noah Thomas - CIN
Mitchell Tinsley - CIN
Ke'Shawn Williams - CIN
Colbie Young - CIN
Malachi Corley - CLE
Luke Floriea - CLE
Gage Larvadain - CLE
Tylan Wallace - CLE
Kole Wilson - CLE
Camden Brown - DAL
Jordan Hudson - DAL
Tyler Johnson - DAL
Denzel Mims - DAL
Jonathan Mingo - DAL
Anthony Smith - DAL
Jaden Smith - DAL
Marquez Valdes-Scantling - DAL
Michael Bandy - DEN
Lil'Jordan Humphrey - DEN
Kolbe Katsis - DEN
Dane Key - DEN
Joseph Manjack - DEN
Cameron Ross - DEN
Kyrese Rowan - DEN
Tarik Black - DET
Malik Cunningham - DET
Greg Dortch - DET
Lucky Jackson - DET
Tom Kennedy - DET
Dominic Lovett - DET
Tay Martin - DET
Jackson Meeks - DET
Chris Hilton Jr. - GB
Kisean Johnson - GB
Bo Melton - GB
Skyy Moore - GB
Isaiah Neyor - GB
Kaden Prather - GB
Will Sheppard - GB
J. Michael Sturdivant - GB
Lewis Bond - HOU
Josh Kelly - HOU
Zay Jones - HOU
Treyvhon Saunders - HOU
Sterling Shepard - HOU
Justin Watson - HOU
Jared Wayne - HOU
Deion Burks - IND
Anthony Gould - IND
Sahmir Hagans - IND
D.J. Montgomery - IND
Ben Nikkel - IND
Coleman Owen - IND
Eli Pancol - IND
Raylen Sharpe - IND
Laquon Treadwell - IND
Nick Westbrook-Ikhine - IND
Brady Boyd - JAX
Chandler Brayboy - JAX
Josh Cameron - JAX
Tim Jones - JAX
Trebor Pena - JAX
Austin Trammell - JAX
C.J. Williams - JAX
Michael Wortham - JAX
Andrew Armstrong - KC
Jacob De Jesus - KC
Omari Evans - KC
Jimmy Holiday - KC
Xavier Loyd - KC
Nikko Remigio - KC
Jalen Royals - KC
Jeff Weimer - KC
Sincere Brown - LAC
Dalevon Campbell - LAC
Liam Clifford - LAC
Derius Davis - LAC
Gary Jennings - LAC
JaQuae Jackson - LAC
KeAndre Lambert-Smith - LAC
Devonte Ross - LAC
Brenen Thompson - LAC
Alex Bachman - LAR
CJ Daniels - LAR
Tru Edwards - LAR
Konata Mumpfield - LAR
Brennan Presley - LAR
Tyler Scott - LAR
Xavier Smith - LAR
Jordan Whittington - LAR
Phillip Dorsett - LV
Brandon Johnson - LV
Shedrick Jackson - LV
Chase Roberts - LV
Deven Thompkins - LV
Dont'e Thornton Jr. - LV
Dareke Young - LV
E.J. Williams Jr. - LV
Kevin Coleman Jr. - MIA
A.J. Henning - MIA
Ryan Miller - MIA
Donaven McCulley - MIA
Terrace Marshall Jr. - MIA
Jalen Reagor - MIA
Theo Wease Jr. - MIA
Dillon Bell - MIN
Michael Briscoe - MIN
Terrill Davis - MIN
Tai Felton - MIN
Dontae Fleming - MIN
Jeshaun Jones - MIN
Myles Price - MIN
Trayvon Rudolph - MIN
Marcus Sanders Jr. - MIN
Efton Chism III - NE
Nick DeGennaro - NE
Cameron Dorner - NE
Tejhaun Palmer - NE
Kyle Williams - NE
Kevin Austin Jr. - NO
Ronnie Bell - NO
Barion Brown - NO
Bryce Lance - NO
Jalen Moreno-Cropper - NO
Trey Palmer - NO
Brock Rechsteiner - NO
Mason Tipton - NO
Odell Beckham Jr. - NYG
Braxton Berrios - NYG
Dalen Cambre - NYG
Xavier Gipson - NYG
Isaiah Hodgins - NYG
Jalin Hyatt - NYG
Kobe Prentice - NYG
Junior Bergen - NYJ
Cam Camper - NYJ
Malik McClain - NYJ
Tim Patrick - NYJ
Jamaal Pritchett - NYJ
Quincy Skinner Jr. - NYJ
Arian Smith - NYJ
Darius Cooper - PHI
Britain Covey - PHI
Danny Gray - PHI
Elijah Moore - PHI
Samori Toure - PHI
Tahj Washington - PHI
Quez Watkins - PHI
Jakobie Keeney-James - PIT
Cornell Powell - PIT
Ben Skowronek - PIT
Brandon Smith - PIT
Levi Wentz - PIT
Kaden Wetjen - PIT
Isaiah Winstead - PIT
Roman Wilson - PIT
Jake Bobo - SEA
Irvin Charles - SEA
Montorie Foster Jr. - SEA
Emmanuel Henderson Jr. - SEA
Julian Hicks - SEA
Velus Jones Jr. - SEA
Rashad Rochelle - SEA
Cody White - SEA
Ricky White III - SEA
Jacob Cowing - SF
Wesley Grimes - SF
KhaDarel Hodge - SF
Trenton Irwin - SF
Will Pauling - SF
Malik Turner - SF
Jordan Watkins - SF
Garrett Greene - TB
Matthew Henry - TB
Jha'Quan Jackson - TB
Kameron Johnson - TB
Tez Johnson - TB
Dean Patterson IV - TB
Eric Rivers Jr. - TB
David Sills - TB
Hank Beatty - TEN
Courtney Jackson - TEN
Mason Kinsey - TEN
Lance McCutcheon - TEN
Tyren Montgomery - TEN
Bryce Oliver - TEN
K.J. Osborn - TEN
Xavier Restrepo - TEN
Jaden Bradley - WAS
Jacoby Jones - WAS
Van Jefferson - WAS
Jaylin Lane - WAS
Nick Nash - WAS
Tyreek Hill - Free Agent
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
Rivaldo Fairweather - ARI
Jameson Geers - ARI
Shawn Bowman - ARI
Nick Muse - ATL
Joshua Simon - ATL
Jack Velling - ATL
Ty Pezza - BAL
Feleipe Franks - CAR
Caden Prieskorn - CAR
Stephen Carlson - CHI
Qadir Ismail - CHI
Hayden Large - CHI
Josh Kattus - CIN
Princeton Fant - DAL
DJ Rogers - DAL
Caleb Lohner - DEN
Thomas Gordon - DET
Zach Horton - DET
McCallan Castles - GB
Jonnu Smith - GB
Messiah Swinson - GB
Thomas Yassmin - GB
Louis Hansen - HOU
Brevin Jordan - HOU
Layne Pryor - HOU
Pharaoh Brown - IND
JJ Galbreath - IND
Tyler Moore - IND
Carson Towt - IND
Patrick Herbert - JAX
Quintin Morris - JAX
Jake Briningstool - KC
Mason Pline - KC
Tre Watson - KC
Patrick Gurd - LV
Albert Okwuegbunam - LV
Carter Runyon - LV
Jerand Bradley - LAC
Johnny Pascuzzi - LAC
Evan Svoboda - LAC
Rohan Jones - LAR
Mark Redman - LAR
Dan Villari - LAR
Jeremiah Franklin - MIA
Cole Turner - MIA
Gavin Bartholomew - MIN
Bryson Nesbit - MIN
Marshall Lang - MIN
Matt Lauter - MIN
Tanner Arkin - NE
Jack Westover - NE
Julian Hill - NE
Cody Hardy - NO
Treyton Welch - NO
Josiah Deguara - NYG
Thomas Fidone II - NYG
Chase Curtis - NYJ
Connor Hulstein - NYJ
E.J. Jenkins - PHI
Lance Mason - PIT
Lake McRee - PIT
Robert Tonyan - PIT
Khalil Dinkins - SF
Brayden Willis - SF
Nick Kallerup - SEA
Kenny Fletcher Jr. - TB
Bauer Sharp - TB
David Martin-Robinson - TEN
Jaren Kanak - TEN
Joel Wilson - TEN
Lawrence Cager - WAS
Tre' McKitty - WAS
Quentin Moore - WAS
Colson Yankoff - WAS
"""

# The following 74 entries were added 2026-08-30 during the same active-
# roster completeness pass as the WR list above -- notable signings
# (Jonnu Smith, Josiah Deguara) plus 3rd/4th/5th-string depth a fantasy-
# relevant source naturally skips. Sequential ranks here (TE131+) are not
# a scouted order, just "comes after the real rankings."
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
