/* ---- English / French. One layer translates every text node, placeholder and chart label, including text the
   page writes later (estimates, explanations, suggestions), so new features stay covered. Numbers switch to the
   French-Canadian format (1 050 000 $). The choice is remembered per browser. ---- */
const FR_EXACT={
"Does it come with parking?":"Avec stationnement?","A storage locker?":"Un casier de rangement?","No parking":"Sans stationnement","Parking (1)":"Stationnement (1)","Parking (2)":"Stationnement (2)","Map":"Carte","Satellite":"Satellite","Street View":"Street View","2 spaces":"2 places","1 space":"1 place",
"Benchmark Home Value":"Valeur repère de votre propriété",
"All provinces & territories · 2016 – Sep 2026":"Toutes les provinces et tous les territoires · 2016 – sept. 2026",
"Answer a few questions to see what your home may be worth today, your estimated equity, and how a renovation could add value.":"Répondez à quelques questions pour connaître la valeur actuelle possible de votre propriété, votre avoir propre estimé et l’effet d’une rénovation sur sa valeur.",
"Address":"Adresse","Your home":"Votre propriété","Your estimate":"Votre estimation",
"Find out what your home may be worth today.":"Découvrez ce que votre propriété pourrait valoir aujourd’hui.",
"Your home address":"Adresse de votre propriété","Province":"Province","Municipality":"Municipalité","Get started":"Commencer",
"Type a few words of your address and pick it from the list.":"Tapez quelques mots de votre adresse et choisissez-la dans la liste.",
"Type your street address, or a postal code. Pick your municipality first if you don't know the postal code.":"Tapez votre adresse ou un code postal. Choisissez d’abord votre municipalité si vous ne connaissez pas le code postal.",
"Tell us about your home":"Parlez-nous de votre propriété","Property type":"Type de propriété","Houses":"Maisons","Condos":"Copropriétés",
"Detached house":"Maison individuelle","Link (detached above grade)":"Maison liée (détachée hors sol)","Semi-detached":"Jumelé",
"Freehold townhouse":"Maison en rangée (pleine propriété)","Duplex (2 units)":"Duplex (2 logements)","Triplex / fourplex":"Triplex / quadruplex",
"Rural home / acreage":"Maison rurale / terre","Cottage / recreational":"Chalet / propriété de loisir","Mobile / manufactured home":"Maison mobile / usinée",
"Condo apartment":"Appartement en copropriété","Condo loft":"Loft en copropriété","Condo townhouse":"Maison en rangée en copropriété",
"Stacked townhouse":"Maison en rangée superposée","Penthouse":"Penthouse","Detached":"Individuelle","Semi":"Jumelé","Townhouse":"En rangée","Condo apt":"Appart. copro.",
"Monthly condo fee ($)":"Frais de copropriété mensuels ($)","Condo details":"Détails de la copropriété","Floor":"Étage","Main view":"Vue principale",
"No notable view":"Aucune vue particulière","City":"Ville","Park / green space":"Parc / espace vert","Water / lake":"Eau / lac","Mountain":"Montagne",
"Locker":"Casier","No":"Non","Yes":"Oui","Building amenities":"Services de l’immeuble","None":"Aucun","Basic (gym, party room)":"De base (gym, salle commune)",
"Full (pool, concierge)":"Complets (piscine, concierge)","Special assessment owing ($)":"Cotisation spéciale due ($)","Reserve fund":"Fonds de prévoyance",
"Healthy":"Bien financé","Low / underfunded":"Faible / sous-financé","Not sure":"Je ne sais pas","Repairs needed":"Réparations nécessaires",
"What you paid ($)":"Prix payé ($)","When you bought":"Date d’achat","Renovations since purchase ($)":"Rénovations depuis l’achat ($)",
"Bedrooms":"Chambres","Bathrooms":"Salles de bain","Living area (sq ft)":"Superficie habitable (pi²)","Condition":"État","Needs work":"Travaux requis",
"Average":"Moyen","Updated":"Mis à jour","Fully renovated":"Entièrement rénové","Parking":"Stationnement","1 space":"1 place","2 spaces":"2 places",
"Lot":"Terrain","Small":"Petit","Typical":"Typique","Large":"Grand","Oversized / ravine":"Très grand / ravin",
"Mortgage balance owing ($)":"Solde hypothécaire ($)","Back":"Retour","See my estimate":"Voir mon estimation",
"Estimated value today":"Valeur estimée aujourd’hui","Estimated home equity":"Avoir propre estimé","Rate for payments (%)":"Taux pour les paiements (%)",
"Amortization":"Amortissement","20 years":"20 ans","25 years":"25 ans","30 years":"30 ans","Could a renovation add value?":"Une rénovation pourrait-elle ajouter de la valeur?",
"Project":"Projet","Kitchen remodel":"Rénovation de cuisine","Bathroom remodel":"Rénovation de salle de bain","Finish basement":"Finition du sous-sol",
"Interior paint":"Peinture intérieure","New flooring":"Nouveaux planchers","Windows & doors":"Portes et fenêtres","Addition":"Agrandissement","Deck or patio":"Terrasse ou patio",
"Budget ($)":"Budget ($)","Edit my answers":"Modifier mes réponses","Copy summary":"Copier le résumé","Summary copied.":"Résumé copié.",
"Select-all is ready: press Ctrl+C to copy.":"Le texte est sélectionné : appuyez sur Ctrl+C pour copier.",
"Indicative only. Values come from public municipal assessment records, the 2021 Census and published regional benchmarks, not from sold listings. Not an appraisal and not suitable for lending decisions.":"À titre indicatif seulement. Les valeurs proviennent des rôles d’évaluation municipaux publics, du Recensement de 2021 et des indices régionaux publiés, et non des ventes inscrites. Ce n’est pas une évaluation et ne convient pas aux décisions de prêt.",
"Benchmark price by type":"Prix repère par type","Year-over-year change":"Variation sur un an","vs. province and region":"par rapport à la province et à la région",
"Monthly carrying cost, 20% down":"Coût mensuel, mise de fonds de 20 %","All municipalities":"Toutes les municipalités","— click a row, click headers to sort":"— cliquez sur une ligne, ou sur un titre pour trier",
"Municipality ":"Municipalité ","Benchmark":"Repère","1Y":"1 an","3Y":"3 ans","5Y":"5 ans","10Y":"10 ans","vs peak":"vs sommet",
"1-year change":"Variation sur 1 an","5-year change":"Variation sur 5 ans","Market trends":"Tendances du marché",
"Clear address":"Effacer l’adresse","Start typing, e.g. 15 Deermeade":"Commencez à taper, p. ex. 15 Deermeade","e.g. 850000":"p. ex. 850000",
"optional, for your equity":"facultatif, pour votre avoir propre",
"Refine my estimate":"Préciser mon estimation","Show my estimate":"Voir mon estimation","Can't find it? Choose your province and municipality":"Introuvable? Choisissez votre province et votre municipalité",
"Legal description":"Description légale","Street photos near this address":"Photos de rue près de cette adresse","What can I build here?":"Que puis-je construire ici?","Added units":"Logements ajoutés","Potential rent income":"Revenus de location potentiels","Typical build cost":"Coût de construction typique","Possible equity created":"Avoir propre potentiellement créé","Median household income":"Revenu médian des ménages","Homeowners":"Propriétaires","Population growth 2016–21":"Croissance démographique 2016–2021","Median age":"Âge médian","University degree":"Diplôme universitaire","Commute by transit":"Transport en commun pour le travail","Detached houses":"Maisons individuelles","Homes built before 1961":"Logements construits avant 1961","Owner monthly costs":"Frais mensuels des propriétaires","Renter monthly costs":"Frais mensuels des locataires","Bars show how this block compares with all Canadian neighbourhoods.":"Les barres comparent cet îlot à l’ensemble des quartiers canadiens.","Non-residential or commercial building":"Bâtiment non résidentiel ou commercial","Commercial / mixed-use zoning":"Zonage commercial ou mixte","Value of that income (5% cap rate, 30% costs)":"Valeur de ce revenu (taux de capitalisation 5 %, frais 30 %)","Homes near you on this street":"Propriétés voisines dans cette rue","Print / Save as PDF":"Imprimer / Enregistrer en PDF","How we got this number":"Comment nous avons obtenu ce chiffre",
"Property":"Propriété","Assessment history":"Historique des évaluations","Location":"Emplacement","Equity and borrowing":"Avoir propre et emprunt","Estimated equity":"Avoir propre estimé",
"Type":"Type","Living area":"Superficie habitable","Street View ↗":"Street View ↗","Google Maps ↗":"Google Maps ↗","Satellite ↗":"Satellite ↗","Bing Streetside ↗":"Bing Streetside ↗","Instant estimate":"Estimation instantanée",
"Postal area":"Région postale","Postal area median (Census, today)":"Médiane de la région postale (Recensement, aujourd’hui)",
"Typical year built":"Année de construction typique","Searching…":"Recherche…","Looking up this property…":"Recherche de cette propriété…",
"Home-equity line available (65% limit)":"Marge sur valeur domiciliaire disponible (limite de 65 %)","Interest-only payment on full line / mo":"Paiement des intérêts seulement sur la marge complète / mois",
"Refinance cash-out available (80%)":"Liquidités disponibles par refinancement (80 %)","New mortgage at 80% / mo":"Nouveau prêt à 80 % / mois","Current balance payment / mo":"Paiement sur le solde actuel / mois",
"Add your mortgage balance on the previous step to see your equity.":"Ajoutez votre solde hypothécaire à l’étape précédente pour voir votre avoir propre.",
"Answer a few questions to sharpen the estimate.":"Répondez à quelques questions pour préciser l’estimation.",
"Found records for this street. Answer a few questions to sharpen the estimate.":"Nous avons des données pour cette rue. Répondez à quelques questions pour préciser l’estimation.",
"Pick your municipality below or add the postal code, then type the street again.":"Choisissez votre municipalité ci-dessous ou ajoutez le code postal, puis retapez la rue.",
"The local data didn't load. Estimates will use the regional benchmarks only.":"Les données locales n’ont pas pu être chargées. Les estimations utiliseront seulement les indices régionaux.",
"Rendered with Chart.js":"Affiché avec Chart.js","Rendered with built-in canvas fallback":"Affiché avec le moteur de secours intégré","Shown as a table (chart renderers unavailable)":"Affiché sous forme de tableau (graphiques indisponibles)",
"Roof replacement":"Remplacement du toit","Furnace or A/C":"Fournaise ou climatiseur","Windows":"Fenêtres","Foundation or water leaks":"Fondation ou infiltrations d’eau",
"Old wiring or panel":"Câblage ou panneau électrique désuet","Old plumbing":"Plomberie désuète","Water damage or mould":"Dégâts d’eau ou moisissure","Dated kitchen":"Cuisine désuète",
"Dated bathroom(s)":"Salle(s) de bain désuète(s)","Worn flooring":"Planchers usés","Needs painting":"Peinture à refaire","Siding, deck or driveway":"Revêtement, terrasse ou entrée",
"Condo":"Copro.","Town":"Rangée","Mortgage payment / mo":"Paiement hypothécaire / mois",
"Greater Toronto & Hamilton":"Grand Toronto et Hamilton","Ottawa region":"Région d’Ottawa","Southwestern Ontario":"Sud-ouest de l’Ontario","Central & Eastern Ontario":"Centre et est de l’Ontario",
"Northern Ontario":"Nord de l’Ontario","Calgary region":"Région de Calgary","Edmonton region":"Région d’Edmonton","Rest of Alberta":"Reste de l’Alberta","Metro Vancouver":"Grand Vancouver",
"Rest of British Columbia":"Reste de la Colombie-Britannique","Saskatchewan & Manitoba":"Saskatchewan et Manitoba","Greater Montréal":"Grand Montréal","Rest of Québec":"Reste du Québec",
"Atlantic Canada":"Canada atlantique","Northern territories":"Territoires du Nord","British Columbia":"Colombie-Britannique","Newfoundland and Labrador":"Terre-Neuve-et-Labrador",
"Nova Scotia":"Nouvelle-Écosse","New Brunswick":"Nouveau-Brunswick","Prince Edward Island":"Île-du-Prince-Édouard","Northwest Territories":"Territoires du Nord-Ouest","Québec":"Québec"};
// phrases inside longer, data-filled sentences (longest first)
const FR_PHRASE=[["benchmark","repère"],
["2021 Census values for your block and postal area, moved to today and split by property type using local assessment ratios","valeurs du Recensement de 2021 pour votre îlot et votre région postale, mises à jour à aujourd’hui et réparties par type selon les ratios d’évaluation locaux"],
["From your neighbourhood's Census values and local assessment ratios.","D’après les valeurs du Recensement de votre quartier et les ratios d’évaluation locaux."],
["Tell us about your home to sharpen it.","Parlez-nous de votre propriété pour la préciser."],
["From real assessments on your street.","D’après les évaluations réelles de votre rue."],
["From assessments in your postal area.","D’après les évaluations de votre région postale."],
["From public Census and assessment data","D’après les données publiques du Recensement et des évaluations"],
["From real assessment records","D’après les rôles d’évaluation réels"],
["averaged with your purchase price indexed to today","moyenne avec votre prix d’achat indexé à aujourd’hui"],
["Typical error at this level:","Erreur typique à ce niveau :"],
["moved to today with the regional price index","mise à jour avec l’indice régional des prix"],
["Your home's details are applied on top.","Les caractéristiques de votre propriété sont appliquées ensuite."],
["2021 Census median home value","valeur médiane des logements au Recensement de 2021"],
["No records for this street. We'll use postal area","Aucune donnée pour cette rue. Nous utiliserons la région postale"],
["% of the estimated value. Borrowing room up to 80% of value:","% de la valeur estimée. Capacité d’emprunt jusqu’à 80 % de la valeur :"],
["estimated value added;","valeur ajoutée estimée;"],["kitchens typically recover 65-80% of cost","une cuisine récupère généralement 65 à 80 % du coût"],
["bathrooms typically recover 60-80%","une salle de bain récupère généralement 60 à 80 %"],["finished basements recover 50-70%","un sous-sol fini récupère 50 à 70 %"],
["paint often recovers its full cost","la peinture récupère souvent tout son coût"],["flooring recovers 60-80%","les planchers récupèrent 60 à 80 %"],
["windows recover 45-65%","les fenêtres récupèrent 45 à 65 %"],["additions recover 45-65%","un agrandissement récupère 45 à 65 %"],["decks recover 50-70%","une terrasse récupère 50 à 70 %"],
["in this neighbourhood (Census block","dans ce quartier (îlot du Recensement"],["Neighbourhood median (block","Médiane du quartier (îlot"],
["homes on record","propriétés au rôle"],["on this street","dans cette rue"],["typical · ","typique · "],["on record","au rôle"],
["adjusted for your","ajustée pour vos"],["sq ft","pi²"],["assessments","évaluations"],["typical detached house","maison individuelle typique"],
["typical condo townhouse","maison en rangée en copropriété typique"],["typical condo","copropriété typique"],["typical townhouse","maison en rangée typique"],
["typical semi","jumelé typique"],["typical duplex","duplex typique"],["typical plex","plex typique"],["typical mobile home","maison mobile typique"],
["in postal area","dans la région postale"],[" is "," vaut "],[" today"," aujourd’hui"],["Range ","Fourchette "],["Your neighbourhood (2021 Census block","Votre quartier (îlot du Recensement de 2021"],["Zoning:","Zonage :"],["Up to ","Jusqu’à "],[" homes on this lot"," logements sur ce terrain"],[" home on this lot"," logement sur ce terrain"],["Typical rent per unit (CMHC","Loyer typique par logement (SCHL"],["/mo","/mois"],["/yr","/an"],["From the city's open property data. Check the full by-law before building.","Selon les données foncières ouvertes de la ville. Consultez le règlement complet avant de construire."],["Residential value models fit it less well; a commercial appraisal or income approach is more reliable.","Les modèles résidentiels conviennent moins bien; une évaluation commerciale ou par le revenu est plus fiable."],["Statistics Canada's address register marks this address as non-residential.","Le registre d’adresses de Statistique Canada indique que cette adresse est non résidentielle."],["Financing: Canada's Secondary Suite Refinance Program (2025) allows refinancing up to 90% of the finished value with a 30-year amortization to add a suite; multiplexes of 5+ units can use CMHC MLI Select. Estimates only; confirm zoning, servicing, permits and costs.","Financement : le Programme de refinancement pour logements accessoires (2025) permet de refinancer jusqu’à 90 % de la valeur une fois les travaux terminés, sur 30 ans, pour ajouter un logement; les immeubles de 5 logements et plus peuvent utiliser MLI Select de la SCHL. Estimations seulement; vérifiez le zonage, les services, les permis et les coûts."],["Assessments usually land within 5–10% of market value.","Les évaluations se situent généralement à 5–10 % de la valeur marchande."],["From this home's own assessment","D’après l’évaluation de cette propriété"],["assessed at","évaluée à"],[" roll, combined with"," au rôle, combinée avec"],["the street's typical value of","la valeur typique de la rue de"],["the neighbourhood's typical value of","la valeur typique du quartier de"],["and your purchase price indexed to today","et votre prix d’achat indexé à aujourd’hui"],[" on the "," au rôle "],[" since "," depuis "],["Assessed ","Évaluée "],["Home value report","Rapport sur la valeur de la propriété"],["The report is shown below. If no print dialog opened, this preview blocks printing; Print / Save as PDF works when the page is on your own website.","Le rapport s’affiche ci-dessous. Si la fenêtre d’impression ne s’est pas ouverte, cet aperçu bloque l’impression; Imprimer / Enregistrer en PDF fonctionne lorsque la page est sur votre propre site."],["Coordinates","Coordonnées"],["Map pin:","Repère :"],["Postal area ","Région postale "],
["Repairs needed","Réparations nécessaires"],["Special assessment","Cotisation spéciale"],["Amenities","Services"],["View","Vue"],["Floor ","Étage "],
["deducted","déduits"],["confidence","confiance"],["area benchmark","repère du secteur"],["Based on","Fondé sur"],["High","Élevée"],["Medium","Moyenne"],["Low","Faible"],
["Indicative only — not an appraisal.","À titre indicatif seulement — ce n’est pas une évaluation."],["Home value estimate:","Valeur estimée de la propriété :"],["Equity:","Avoir propre :"],
["avg","moy."],[" on "," sur "],["typical ","typique "],["(block ","(îlot "],[": ",": "]];
FR_PHRASE.push(["Detached benchmark","Repère maison individuelle"],["Semi benchmark","Repère jumelé"],["Town benchmark","Repère maison en rangée"],["Condo benchmark","Repère copropriété"],
["vs peak","vs sommet"]);
// region and province names also appear inside longer lines ("Greater Toronto & Hamilton · Ontario")
for(const k of ["Greater Toronto & Hamilton","Ottawa region","Southwestern Ontario","Central & Eastern Ontario","Northern Ontario","Calgary region","Edmonton region","Rest of Alberta","Metro Vancouver","Rest of British Columbia","Saskatchewan & Manitoba","Greater Montréal","Rest of Québec","Atlantic Canada","Northern territories","British Columbia","Newfoundland and Labrador","Nova Scotia","New Brunswick","Prince Edward Island","Northwest Territories"])FR_PHRASE.push([k,FR_EXACT[k]]);
FR_PHRASE.sort((a,b)=>b[0].length-a[0].length);
const MONTHS_FR={Jan:"janv.",Feb:"févr.",Mar:"mars",Apr:"avr.",May:"mai",Jun:"juin",Jul:"juil.",Aug:"août",Sep:"sept.",Oct:"oct.",Nov:"nov.",Dec:"déc."};
let LANG="en";try{LANG=localStorage.getItem("hve-lang")||(navigator.language||"").slice(0,2)==="fr"&&"fr"||"en";}catch(e){}
const ORIG=new WeakMap(),ORIGA=new WeakMap();
function frMoney(s){return s.replace(/\$(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(K|M)?/g,(m,n,d,u)=>{
  if(u)return n.replace(/,/g," ")+(d?d.replace(".",","):"")+(u==="M"?" M$":" k$");return n.replace(/,/g," ")+" $";});}
function toFr(t){const k=t.trim();if(!k)return t;
  if(FR_EXACT[k])return t.replace(k,FR_EXACT[k]);
  let o=t;for(const [a,b] of FR_PHRASE)if(o.includes(a))o=o.split(a).join(b);
  o=o.replace(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s  ](\d\d)/g,(m,a,b)=>MONTHS_FR[a]+" "+b);
  o=o.replace(/([+\-−]?\d+)\.(\d+)%/g,"$1,$2 %");               // French decimals and spacing before %
  return frMoney(o);}
function trNode(n){if(n.nodeType===3){const p=n.parentNode;if(!p||/^(SCRIPT|STYLE)$/.test(p.nodeName))return;
    if(LANG==="fr"){const cur=n.nodeValue;const was=ORIG.get(n);if(was&&was.fr===cur)return;const fr=toFr(cur);ORIG.set(n,{en:cur,fr});if(fr!==cur)n.nodeValue=fr;}
    else{const was=ORIG.get(n);if(was&&n.nodeValue===was.fr){n.nodeValue=was.en;ORIG.delete(n);}}return;}
  if(n.nodeType!==1)return;
  for(const at of ["placeholder","aria-label","label"]){if(!n.hasAttribute||!n.hasAttribute(at))continue;
    const m=ORIGA.get(n)||{};if(!(at in m))m[at]=n.getAttribute(at);ORIGA.set(n,m);
    n.setAttribute(at,LANG==="fr"?(FR_EXACT[m[at]]||m[at]):m[at]);}
  n.childNodes.forEach(trNode);}
let trBusy=false;
const trObs=new MutationObserver(ms=>{if(trBusy||LANG!=="fr")return;trBusy=true;
  for(const m of ms){if(m.type==="characterData")trNode(m.target);else m.addedNodes.forEach(trNode);}trBusy=false;});
trObs.observe(document.body,{subtree:true,childList:true,characterData:true});
// charts draw on canvas, so translate their labels before drawing
const _render=render;
render=function(id,spec){if(LANG==="fr"){spec={...spec,labels:spec.labels.map(l=>l.replace(/^([A-Z][a-z]{2})/,m=>MONTHS_FR[m]||m)),
  sets:spec.sets.map(s=>({...s,label:toFr(s.label)})),fmt:(f=>v=>frMoney(String(f(v))))(spec.fmt)};}return _render(id,spec);};
function setLang(l){LANG=l;try{localStorage.setItem("hve-lang",l);}catch(e){}document.documentElement.lang=l==="fr"?"fr-CA":"en-CA";
  $("langBtn").textContent=l==="fr"?"English":"Français";$("langBtn").setAttribute("lang",l==="fr"?"en":"fr");
  trBusy=true;trNode(document.body);trBusy=false;market();}
(function(){const b=document.createElement("button");b.id="langBtn";b.type="button";b.className="ghost lang";b.textContent="Français";
  b.addEventListener("click",()=>setLang(LANG==="fr"?"en":"fr"));document.querySelector("header").appendChild(b);
  if(LANG==="fr")setLang("fr");})();
