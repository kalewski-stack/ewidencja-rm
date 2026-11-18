/**
 * EWIDENCJA CZASU PRACY — backend (Google Apps Script)
 * Aplikacja na telefon (Start / Przerwa / Zakończ) -> Arkusz Google -> karta na każdy miesiąc
 * + karta "Razem" + mail dzienny.
 *
 * Wersja 5
 *  - każdy pracownik ma własny link (?k=KLUCZ), imię wstawione na sztywno, bez logowania
 *  - Start / Przerwa / Zakończ zapisują od razu do arkusza; poprawki tylko w obrębie dzisiejszego dnia
 *  - nieobecności (Urlop, L4) zakresem dat, z rodzajem (wypoczynkowy, na żądanie, opieka…)
 *  - widok miesiąca dla pracownika (tylko własne dane), panel Zespół dla Admina
 *  - karta miesiąca w arkuszu jak dotąd + karta "Razem" (pierwsza zakładka) sumująca wszystkie miesiące
 *  - log zmian, ochrona zakładek, karta PDF per osoba
 *
 * Zakładka "Wpisy": kolumny A–K jak w wersji 4, dochodzi L "Zapisał".
 * Ukryte zakładki: "Konfiguracja" (klucze linków), "Linki" (gotowe linki), "Log".
 */

const CONFIG = {
  // ID arkusza — ze środka linku: docs.google.com/spreadsheets/d/TUTAJ_ID/edit
  SHEET_ID: '12lrHey8BjpxgYAkjQmdi_WnmUyrpP_I0Sgxmd8pzYBk',

  // Raport dzienny. Kilka adresów = JEDEN tekst, adresy po przecinku w środku.
  MAIL_KOORDYNATORA: 'kalewski@gmail.com,fundacja@redemptorismissio.org',

  // Pracownicy — dokładnie te imiona trafiają do arkusza i na karty.
  OSOBY: ['Mateusz', 'Tomasz', 'Marysia', 'Anna Ml', 'Anna', 'Natalia', 'Karina', 'Magdalena'],

  // Administratorzy — mają zakładkę "Zespół", wpisują i poprawiają godziny za innych (każda data),
  // drukują karty. Mogą być z listy OSOBY albo osobne konto bez własnej ewidencji.
  ADMINI: ['Admin'],

  // Wymiar etatu. Kogo nie ma na liście, ten pracuje na cały etat. Norma = norma pełna × etat.
  ETATY: { 'Marysia': 0.875, 'Natalia': 0.5 },

  // Urlop wypoczynkowy w roku. URLOP_ROCZNY to wymiar w dniach dla całego etatu; dla niepełnych etatów liczony
  // proporcjonalnie i zaokrąglany w górę (7/8 → 23 dni, 1/2 → 13 dni). Kto ma inny wymiar (20 dni, zaległy urlop
  // z zeszłego roku, dodatkowe dni), ten dostaje wpis w URLOP_WYMIAR (w dniach po 8 h) i to on obowiązuje.
  // Niepełny etat rozliczany jest GODZINOWO (art. 154 § 2 KP): pula = dni × 8 h, a dzień urlopu zużywa tyle
  // godzin, ile wynosi norma dzienna osoby (Natalia: 104 h puli, dzień urlopu = 4 h; Marysia: 184 h, dzień = 7 h).
  URLOP_ROCZNY: 26,
  URLOP_WYMIAR: { },

  // STAN URLOPU przeniesiony z poprzedniej ewidencji: ile przysługuje i ile już wykorzystano, stan na koniec dnia
  // URLOP_STAN_NA. Wpisy "Urlop" w aplikacji PO tej dacie są doliczane, wcześniejsze są już w tych liczbach.
  // Pełny etat w dniach (po 8 h, mogą być połówki), niepełny etat w godzinach. Kto ma wpis tutaj, tego nie dotyczy
  // URLOP_ROCZNY / URLOP_WYMIAR. Działa dla roku z URLOP_STAN_NA; w kolejnym roku wraca zwykły wymiar.
  URLOP_STAN_NA: '2026-11-18',
  URLOP_STAN: {
    'Karina':    { przysluguje: 9,  wykorzystane: 1 },
    'Anna Ml':   { przysluguje: 9,  wykorzystane: 0 },       // Ania Młynarczyk
    'Anna':      { przysluguje: 26, wykorzystane: 26 },      // Ania Mikołajczyk
    'Magdalena': { przysluguje: 14, wykorzystane: 2.5 },
    'Tomasz':    { przysluguje: 24, wykorzystane: 20 },
    'Marysia':   { przyslugujeGodz: 200, wykorzystaneGodz: 120 },   // 7/8 etatu, dzień urlopu = 7 h
    'Natalia':   { przyslugujeGodz: 56,  wykorzystaneGodz: 0 }      // 1/2 etatu, dzień urlopu = 4 h
  },

  // Płatne nieobecności zaliczane do przepracowanych godzin: każdy taki dzień = norma dzienna (8 h × etat),
  // norma miesiąca zostaje pełna. Urlop wypoczynkowy jest płatny, więc dzień urlopu "wyrabia" 8 h jak dzień pracy.
  // Kto chce, żeby np. L4 nie wchodziło w przepracowane (tylko obniżało normę), usuwa je z tej listy.
  NIEOBECNOSC_ZALICZANA: ['Urlop', 'L4', 'Inne', 'Wolne'],

  // Rozliczenie TYGODNIOWE zamiast dziennego (dla niepełnych etatów z ruchomym grafikiem). Norma tygodnia =
  // dni robocze tygodnia × norma dzienna (1/2 etatu: 5 × 4 h = 20 h). Nadgodziny i braki liczone z sumy tygodnia:
  // 30 h w tygodniu = +10 h nadgodzin, 18 h = 2 h luki (pokrywanej z banku nadgodzin). Godziny z soboty i niedzieli
  // wchodzą do sumy tygodnia. Tydzień = poniedziałek–niedziela, cięty na granicy miesiąca.
  ROZLICZENIE_TYGODNIOWE: ['Natalia'],

  // Bank nadgodzin. Od miesiąca BANK_NADGODZIN_OD saldo liczy się NARASTAJĄCO: stan z poprzedniego miesiąca
  // + nadwyżki bieżącego miesiąca − krótsze dni i odbiory. BANK_NADGODZIN_START to stan wyjściowy z poprzedniej
  // ewidencji (godziny, stan na koniec miesiąca poprzedzającego BANK_NADGODZIN_OD). Kogo nie ma, zaczyna od 0.
  // Kafelek "Nadgodziny" w aplikacji pokazuje aktualne saldo banku; bank nie schodzi poniżej 0, brak ponad bank
  // to "Niedogodziny" danego miesiąca. Miesiące sprzed BANK_NADGODZIN_OD liczone są jak dotąd, każdy osobno.
  BANK_NADGODZIN_OD: '2026-10',
  BANK_NADGODZIN_START: { 'Anna': 1.5, 'Marysia': 43, 'Tomasz': 190.5, 'Natalia': 12.5, 'Magdalena': 43.5, 'Anna Ml': 0.5, 'Karina': 0.5 },

  // Przerwa na karmienie (art. 187 KP) liczona do czasu pracy. Doliczana automatycznie po zakończeniu dnia:
  // powyżej 6 h faktycznej pracy +1 h, od 4 do 6 h +0,5 h, poniżej 4 h nic.
  PRZERWA_KARMIENIE: ['Magdalena'],

  // Osoby, które pracują także w weekendy i święta (delegacje, parafie). Mogą:
  //  - dopisać godziny pracy z soboty / niedzieli / święta do WEEKEND_DNI_WSTECZ dni wstecz,
  //  - zgłosić dzień "Wolne" (np. piątek) w zamian za pracę w weekend.
  PRACA_W_WEEKEND: ['Tomasz', 'Anna', 'Magdalena', 'Natalia'],
  WEEKEND_DNI_WSTECZ: 7,

  // Miejsca pracy — klikalne przyciski. Można też wpisać własne w polu obok.
  LOKALIZACJE: ['G7', 'J48', 'HO', 'W terenie', 'Delegacja'],
  // Które miejsce liczy się jako praca zdalna w kolumnie "w tym HO".
  LOKALIZACJA_ZDALNA: 'HO',
  // Miejsca, które w zakładce "W pracy" NIE są biurem (osoba pracuje, ale biuro może być zamknięte).
  // Wszystko spoza tej listy (G7, J48, własny wpis) pokazuje się jako obecność w biurze.
  LOKALIZACJE_POZA_BIUREM: ['HO', 'W terenie', 'Delegacja'],

  // Typy nieobecności. Powód pracownik wpisuje w polu "Powód / uwagi" (trafia do kolumny Uwagi w arkuszu).
  // Listy w nawiasach to opcjonalne podpowiedzi-przyciski; puste = tylko wolne pole tekstowe.
  //  - Odbiór nadgodzin: dzień wolny za wypracowane nadgodziny, 0 h pracy, norma bez zmian.
  //  - Inne: dni płatne poza urlopem i L4 (oddanie krwi, opieka art. 188 KP, szkolenie…), powód obowiązkowy.
  //  - Wolne: dzień wolny w zamian za pracę w weekend, tylko osoby z PRACA_W_WEEKEND (admin dla każdego).
  RODZAJE: {
    'Urlop': [],
    'L4': [],
    'Odbiór nadgodzin': [],
    'Inne': [],
    'Wolne': []
  },

  /* --- NORMA GODZIN --- */
  // true = (dni robocze − święta) × 8, zgodnie z Kodeksem pracy. false = zawsze NORMA_MIESIECZNA.
  NORMA_WG_DNI_ROBOCZYCH: true,
  NORMA_MIESIECZNA: 160,

  /* --- ZAOKRĄGLANIE CZASU PRACY --- */
  // 0 = czas liczony co do minuty (godziny w podsumowaniu równe różnicy start–koniec minus przerwy).
  // 30 = suma dnia zaokrąglana do pełnych 30 minut: reszta do 25 min w dół, od 26 min w górę
  //      (1–25 min -> 0:00, 26–55 min -> 0:30, 56 min – 1 h 25 min -> 1:00). Wtedy aplikacja pokazuje
  //      obok siebie czas faktyczny i liczony.
  ZAOKRAGLANIE_MIN: 0,
  ZAOKRAGLANIE_W_GORE_OD: 26,

  /* --- ZASADY --- */
  MAX_GODZIN_DOBA: 16,          // powyżej aplikacja prosi o potwierdzenie
  NIEOBECNOSC_DNI_WSTECZ: 35,   // L4 / urlop można zgłosić do tylu dni wstecz…
  NIEOBECNOSC_DNI_NAPRZOD: 120, // …i do tylu dni naprzód
  KARTA_PO_ZAPISIE: true,       // po każdym zapisie odśwież kartę miesiąca i "Razem" (ok. 2–3 s dłużej)
  RAPORT_TYLKO_DNI_ROBOCZE: true,

  // Adres aplikacji PWA (GitHub Pages). Puste = linki prowadzą prosto do skryptu (wersja wbudowana).
  // Przykład: 'https://fundacjarm.github.io/ewidencja/'
  APP_URL: 'https://kalewski-stack.github.io/ewidencja-rm/',

  STREFA: 'Europe/Warsaw',
  ARKUSZ_WPISY: 'Wpisy',
  ARKUSZ_KONFIG: 'Konfiguracja',
  ARKUSZ_LINKI: 'Linki',
  ARKUSZ_LOG: 'Log',
  ARKUSZ_RAZEM: 'Razem'
};

const NAGLOWKI = ['Zapisano', 'Data', 'Imię', 'Typ dnia', 'Start', 'Koniec', 'Przerwa od', 'Przerwa do',
                  'Miejsce pracy', 'Godziny', 'Uwagi', 'Zapisał'];
const KOL = { ZAPISANO: 0, DATA: 1, IMIE: 2, TYP: 3, START: 4, KONIEC: 5, PRZ_OD: 6, PRZ_DO: 7,
              MIEJSCE: 8, GODZINY: 9, UWAGI: 10, ZAPISAL: 11 };

const TYPY = ['Praca', 'Urlop', 'L4', 'Wolne', 'Odbiór nadgodzin', 'Inne'];
const MIESIACE_PL = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec',
                     'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'];
const DNI_PL = ['nd', 'pon', 'wt', 'śr', 'czw', 'pt', 'sob'];

/* ------------------------------------------------------------------ */
/* MENU W ARKUSZU                                                      */
/* ------------------------------------------------------------------ */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Ewidencja')
    .addItem('Przelicz bieżący miesiąc', 'przeliczBiezacyMiesiac')
    .addItem('Przelicz wybrany miesiąc…', 'przeliczWybranyMiesiac')
    .addItem('Przelicz wszystkie miesiące + Razem', 'przeliczWszystkieMiesiace')
    .addSeparator()
    .addItem('Linki pracowników (pokaż / uzupełnij)', 'menuLinki')
    .addItem('Unieważnij link osoby…', 'menuUniewaznijLink')
    .addSeparator()
    .addItem('Zabezpiecz zakładki', 'zabezpieczArkusze')
    .addItem('Ustaw raport dzienny 18:30', 'ustawAutomatyczneRaporty')
    .addToUi();
}

function przeliczBiezacyMiesiac() {
  const m = dzisStr_().slice(0, 7);
  zbudujKarteMiesiaca_(m, true);
  zbudujKarteRazem_();
  SpreadsheetApp.getActive().toast('Karta ' + m + ' i Razem przeliczone.', 'Ewidencja', 5);
}

function przeliczWybranyMiesiac() {
  const ui = SpreadsheetApp.getUi();
  const odp = ui.prompt('Który miesiąc?', 'Wpisz w formacie RRRR-MM, np. 2026-07', ui.ButtonSet.OK_CANCEL);
  if (odp.getSelectedButton() !== ui.Button.OK) return;
  const m = odp.getResponseText().trim();
  if (!/^\d{4}-\d{2}$/.test(m)) { ui.alert('Zły format. Poprawnie: 2026-07'); return; }
  zbudujKarteMiesiaca_(m, true);
  zbudujKarteRazem_();
}

function przeliczWszystkieMiesiace() {
  const miesiace = miesiaceZWpisami_();
  miesiace.forEach(function (m) { zbudujKarteMiesiaca_(m, false); });
  zbudujKarteRazem_();
  SpreadsheetApp.getActive().toast('Przeliczono: ' + miesiace.join(', ') + ' + Razem', 'Ewidencja', 6);
}

function menuLinki() {
  const sh = zbudujLinki_();
  SpreadsheetApp.getActive().setActiveSheet(sh);
  SpreadsheetApp.getUi().alert('Linki są w zakładce „Linki”. Każdej osobie wyślij tylko jej link. ' +
    'Link działa jak klucz — kto go ma, ten wpisuje godziny tej osoby.');
}

function menuUniewaznijLink() {
  const ui = SpreadsheetApp.getUi();
  const odp = ui.prompt('Unieważnij link', 'Imię osoby (dokładnie jak w CONFIG):', ui.ButtonSet.OK_CANCEL);
  if (odp.getSelectedButton() !== ui.Button.OK) return;
  const imie = odp.getResponseText().trim();
  if (!osobaIstnieje_(imie)) { ui.alert('Nie ma takiej osoby: ' + imie); return; }
  nowyKlucz_(imie);
  log_('arkusz', 'nowy link', '', imie, '');
  zbudujLinki_();
  ui.alert('Stary link „' + imie + '” już nie działa. Nowy jest w zakładce „Linki”.');
}

/** Chroni zakładki przed ręczną edycją przez inne osoby z dostępem do arkusza; ukrywa techniczne. */
function zabezpieczArkusze() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  [arkuszWpisow_(), arkuszKonfig_(), arkuszLog_(), zbudujLinki_()].forEach(function (sh) {
    sh.getProtections(SpreadsheetApp.ProtectionType.SHEET).forEach(function (p) { p.remove(); });
    const p = sh.protect().setDescription('Ewidencja — edycja tylko przez aplikację');
    p.removeEditors(p.getEditors());
    if (p.canDomainEdit()) p.setDomainEdit(false);
  });
  [CONFIG.ARKUSZ_KONFIG, CONFIG.ARKUSZ_LOG, CONFIG.ARKUSZ_LINKI].forEach(function (n) {
    const sh = ss.getSheetByName(n); if (sh) sh.hideSheet();
  });
  try { SpreadsheetApp.getUi().alert('Zakładki zabezpieczone i ukryte (Konfiguracja, Linki, Log).'); } catch (e) {}
}

/* ------------------------------------------------------------------ */
/* WWW + TOŻSAMOŚĆ Z LINKU                                             */
/* ------------------------------------------------------------------ */

function doGet(e) {
  const k = (e && e.parameter && e.parameter.k) ? String(e.parameter.k) : '';
  const kto = osobaZKlucza_(k);
  if (!kto) {
    return HtmlService.createHtmlOutput(
      '<!DOCTYPE html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;padding:40px 24px;color:#11202B;background:#E9EDF0">' +
      '<h2 style="margin:0 0 8px">Brak dostępu</h2><p>Ten link nie jest przypisany do nikogo albo został unieważniony. ' +
      'Poproś administratora o swój link do ewidencji.</p></body>')
      .setTitle('Ewidencja czasu pracy');
  }
  zapiszOstatnieWejscie_(kto.imie);
  if (CONFIG.APP_URL) {
    const cel = String(CONFIG.APP_URL).replace(/\/?$/, '/') + '?k=' + encodeURIComponent(k);
    return HtmlService.createHtmlOutput(
      '<!DOCTYPE html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<meta http-equiv="refresh" content="0; url=' + cel + '">' +
      '<body style="font-family:Roboto,Arial,sans-serif;padding:40px 24px;color:#383838;background:#F3F1EA">' +
      '<p>Przenoszę do aplikacji… <a href="' + cel + '">Kliknij, jeśli nic się nie dzieje.</a></p></body>')
      .setTitle('Ewidencja czasu pracy');
  }
  const t = HtmlService.createTemplateFromFile('index');
  t.klucz = k;
  t.imie = kto.imie;
  t.admin = kto.admin;
  t.maEwidencje = CONFIG.OSOBY.indexOf(kto.imie) > -1;
  t.osoby = CONFIG.OSOBY;
  t.lokalizacje = CONFIG.LOKALIZACJE;
  t.rodzaje = CONFIG.RODZAJE;
  t.dzisiaj = dzisStr_();
  t.maxGodzin = CONFIG.MAX_GODZIN_DOBA;
  t.etat = CONFIG.ETATY[kto.imie] || 1;
  t.karmienie = CONFIG.PRZERWA_KARMIENIE.indexOf(kto.imie) > -1;
  t.weekend = CONFIG.PRACA_W_WEEKEND.indexOf(kto.imie) > -1;
  t.weekendDni = CONFIG.WEEKEND_DNI_WSTECZ;
  t.weekendowi = CONFIG.PRACA_W_WEEKEND;
  return t.evaluate()
    .setTitle('Ewidencja czasu pracy — ' + kto.imie)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

/* ------------------------------------------------------------------ */
/* API JSON DLA APLIKACJI PWA                                          */
/* ------------------------------------------------------------------ */

/** Funkcje, które aplikacja może wywołać przez API. Pierwszy argument każdej to klucz osoby. */
const API_FUNKCJE = ['konfig', 'stanDnia', 'startPracy', 'przerwaStart', 'przerwaStop', 'koniecPracy', 'poprawDzis',
                     'usunWpis', 'zapiszNieobecnosc', 'zapiszZaKogos', 'mojMiesiac', 'przegladZespolu', 'przeliczKarte',
                     'kartaHtml', 'zapiszKartePdf', 'ktoWPracy'];

/**
 * POST z aplikacji: treść JSON {k, fn, args}. Odpowiedź JSON {ok:true, result} albo {ok:false, error}.
 * Aplikacja wysyła Content-Type text/plain, żeby przeglądarka nie robiła zapytania wstępnego (CORS).
 */
function doPost(e) {
  let odp;
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const fn = String(body.fn || '');
    if (API_FUNKCJE.indexOf(fn) === -1) throw new Error('Nieznana operacja: ' + fn);
    const args = [String(body.k || '')].concat(Array.isArray(body.args) ? body.args : []);
    const wynik = this[fn].apply(null, args);
    odp = { ok: true, result: wynik === undefined ? null : wynik };
  } catch (err) {
    odp = { ok: false, error: String(err && err.message || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(odp)).setMimeType(ContentService.MimeType.JSON);
}

/** Dane startowe dla aplikacji: kim jestem i co pokazać. */
function konfig(k) {
  const o = kto_(k);
  return {
    imie: o.imie, admin: o.admin, maEwidencje: CONFIG.OSOBY.indexOf(o.imie) > -1,
    osoby: CONFIG.OSOBY, lokalizacje: CONFIG.LOKALIZACJE, rodzaje: CONFIG.RODZAJE,
    dzisiaj: dzisStr_(), maxGodzin: CONFIG.MAX_GODZIN_DOBA,
    etat: CONFIG.ETATY[o.imie] || 1,
    karmienie: CONFIG.PRZERWA_KARMIENIE.indexOf(o.imie) > -1,
    weekend: CONFIG.PRACA_W_WEEKEND.indexOf(o.imie) > -1,
    weekendDni: CONFIG.WEEKEND_DNI_WSTECZ,
    zaokraglanie: Number(CONFIG.ZAOKRAGLANIE_MIN) || 0, zaokraglanieOd: Number(CONFIG.ZAOKRAGLANIE_W_GORE_OD) || 0
  };
}

function osobaIstnieje_(imie) {
  return CONFIG.OSOBY.indexOf(imie) > -1 || CONFIG.ADMINI.indexOf(imie) > -1;
}

/** {imie, admin} albo null. */
function osobaZKlucza_(k) {
  if (!/^[0-9a-f]{40,64}$/.test(String(k || ''))) return null;
  const dane = arkuszKonfig_().getDataRange().getValues();
  for (let i = 1; i < dane.length; i++) {
    if (String(dane[i][1]) === k && osobaIstnieje_(String(dane[i][0]))) {
      const imie = String(dane[i][0]);
      return { imie: imie, admin: CONFIG.ADMINI.indexOf(imie) > -1 };
    }
  }
  return null;
}

/** Każde wywołanie z aplikacji przechodzi tędy. Błąd "SESJA:" = aplikacja każe odświeżyć link. */
function kto_(k) {
  const o = osobaZKlucza_(k);
  if (!o) throw new Error('SESJA: Link nieaktywny. Poproś administratora o nowy.');
  return o;
}

function admin_(k) {
  const o = kto_(k);
  if (!o.admin) throw new Error('Tylko administrator.');
  return o;
}

/* --- zakładka Konfiguracja: Imię | Klucz | Utworzono | Ostatnie wejście --- */

function arkuszKonfig_() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let sh = ss.getSheetByName(CONFIG.ARKUSZ_KONFIG);
  if (!sh) {
    sh = ss.insertSheet(CONFIG.ARKUSZ_KONFIG);
    sh.getRange(1, 1, 1, 4).setValues([['Imię', 'Klucz', 'Utworzono', 'Ostatnie wejście']]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.hideSheet();
  }
  return sh;
}

function wierszKonfig_(imie) {
  const dane = arkuszKonfig_().getDataRange().getValues();
  for (let i = 1; i < dane.length; i++) if (String(dane[i][0]) === imie) return { wiersz: i + 1, klucz: String(dane[i][1] || '') };
  return { wiersz: -1, klucz: '' };
}

function losowyKlucz_() {
  return (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');   // 64 znaków hex
}

function nowyKlucz_(imie) {
  const sh = arkuszKonfig_();
  const w = wierszKonfig_(imie);
  const k = losowyKlucz_();
  if (w.wiersz > 0) sh.getRange(w.wiersz, 2, 1, 2).setValues([[k, terazStr_()]]);
  else sh.appendRow([imie, k, terazStr_(), '']);
  return k;
}

function zapiszOstatnieWejscie_(imie) {
  try {
    const w = wierszKonfig_(imie);
    if (w.wiersz > 0) arkuszKonfig_().getRange(w.wiersz, 4).setValue(terazStr_());
  } catch (e) {}
}

/** Uzupełnia brakujące klucze i wypisuje gotowe linki do zakładki "Linki". */
function zbudujLinki_() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let url = '';
  try { url = ScriptApp.getService().getUrl() || ''; } catch (e) {}
  const baza = CONFIG.APP_URL ? String(CONFIG.APP_URL).replace(/\/?$/, '/') : url;
  const wszyscy = CONFIG.OSOBY.concat(CONFIG.ADMINI.filter(function (a) { return CONFIG.OSOBY.indexOf(a) === -1; }));
  const wiersze = wszyscy.map(function (imie) {
    let k = wierszKonfig_(imie).klucz;
    if (!k) k = nowyKlucz_(imie);
    const link = baza ? baza + '?k=' + k : '(wdróż aplikację jako „Aplikacja internetowa”, potem uruchom ponownie) ?k=' + k;
    return [imie, CONFIG.ADMINI.indexOf(imie) > -1 ? 'administrator' : 'pracownik', link, k];
  });
  let sh = ss.getSheetByName(CONFIG.ARKUSZ_LINKI);
  if (!sh) sh = ss.insertSheet(CONFIG.ARKUSZ_LINKI);
  sh.clear();
  sh.getRange(1, 1, 1, 5).setValues([['Imię', 'Rola', 'Link do aplikacji (wyślij tylko tej osobie)', 'Klucz (do wpisania ręcznie)', 'Kod QR']]).setFontWeight('bold');
  if (wiersze.length) {
    sh.getRange(2, 1, wiersze.length, 4).setValues(wiersze);
    const qr = wiersze.map(function (w, i) { return ['=IMAGE("https://quickchart.io/qr?size=300&text=" & ENCODEURL(C' + (i + 2) + '))']; });
    sh.getRange(2, 5, wiersze.length, 1).setFormulas(qr);
    sh.setRowHeights(2, wiersze.length, 150);
  }
  sh.setColumnWidth(1, 120); sh.setColumnWidth(2, 110); sh.setColumnWidth(3, 520); sh.setColumnWidth(4, 420); sh.setColumnWidth(5, 160);
  sh.setFrozenRows(1);
  return sh;
}

/* ------------------------------------------------------------------ */
/* DZIŚ: START / PRZERWA / ZAKOŃCZ / POPRAW                            */
/* ------------------------------------------------------------------ */

/** Stan dzisiejszego dnia osoby (+ ewentualnie niezamknięty dzień wczorajszy). */
function stanDnia(k) {
  const o = kto_(k);
  return stanDniaOsoby_(o.imie);
}

/**
 * Zakładka "W pracy": kto ma dziś otwarty dzień pracy (start bez końca) i gdzie. Widzi każdy z linkiem.
 * biuro = miejsce spoza LOKALIZACJE_POZA_BIUREM. Do tego, kto dziś już skończył i kto ma nieobecność.
 */
function ktoWPracy(k) {
  kto_(k);
  const dzis = dzisStr_(), teraz = terazStr_().slice(11);
  const poza = CONFIG.LOKALIZACJE_POZA_BIUREM || [];
  const dzisW = {};
  wszystkieWpisy_().forEach(function (x) {
    if (String(x.r[KOL.DATA]) === dzis) dzisW[String(x.r[KOL.IMIE])] = x.r;
  });
  const wPracy = [], skonczyli = [], nieobecni = [];
  CONFIG.OSOBY.forEach(function (imie) {
    const r = dzisW[imie];
    if (!r) return;
    const typ = String(r[KOL.TYP]);
    if (typ === 'Praca' || typ === 'Zdalnie') {
      if (!r[KOL.START]) return;
      const miejsce = typ === 'Zdalnie' && !r[KOL.MIEJSCE] ? CONFIG.LOKALIZACJA_ZDALNA : String(r[KOL.MIEJSCE] || '');
      if (!r[KOL.KONIEC]) {
        const prz = przerwy_(r);
        wPracy.push({ imie: imie, od: String(r[KOL.START]), miejsce: miejsce, biuro: poza.indexOf(miejsce) === -1,
                      zdalnie: miejsce === CONFIG.LOKALIZACJA_ZDALNA, przerwa: prz.otwarta || '' });
      } else skonczyli.push({ imie: imie, od: String(r[KOL.START]), do: String(r[KOL.KONIEC]), miejsce: miejsce });
    } else nieobecni.push({ imie: imie, typ: typ === 'Chorobowe' ? 'L4' : typ });
  });
  wPracy.sort(function (a, b) { return (b.biuro - a.biuro) || (a.miejsce < b.miejsce ? -1 : a.miejsce > b.miejsce ? 1 : 0) || (a.od < b.od ? -1 : 1); });
  return { dzis: dzis, teraz: teraz, roboczy: dzienRoboczy_(dzis), wPracy: wPracy, skonczyli: skonczyli, nieobecni: nieobecni };
}

function stanDniaOsoby_(imie) {
  const dzis = dzisStr_();
  const wczoraj = dodajDni_(dzis, -1);
  const lista = wszystkieWpisy_().filter(function (x) { return String(x.r[KOL.IMIE]) === imie; });
  const dzisW = lista.filter(function (x) { return String(x.r[KOL.DATA]) === dzis; })[0];
  const wczW = lista.filter(function (x) { return String(x.r[KOL.DATA]) === wczoraj; })[0];
  const otwartyWczoraj = (wczW && String(wczW.r[KOL.TYP]) === 'Praca' && wczW.r[KOL.START] && !wczW.r[KOL.KONIEC]) ? wpisDoObiektu_(wczW.r) : null;

  let ostatnieMiejsce = '';
  for (let i = lista.length - 1; i >= 0; i--) {
    if (lista[i].r[KOL.MIEJSCE]) { ostatnieMiejsce = String(lista[i].r[KOL.MIEJSCE]); break; }
  }
  let nastepny = dodajDni_(dzis, 1);
  while (!dzienRoboczy_(nastepny)) nastepny = dodajDni_(nastepny, 1);
  return {
    dzis: dzis, dzien: dzienTygodnia_(dzis), teraz: terazStr_().slice(11), roboczy: dzienRoboczy_(dzis),
    nastepnyRoboczy: nastepny, jutroRoboczy: nastepny === dodajDni_(dzis, 1),
    wpis: dzisW ? wpisDoObiektu_(dzisW.r) : null,
    otwartyWczoraj: otwartyWczoraj,
    ostatnieMiejsce: ostatnieMiejsce,
    etat: CONFIG.ETATY[imie] || 1,
    karmienie: CONFIG.PRZERWA_KARMIENIE.indexOf(imie) > -1,
    weekend: CONFIG.PRACA_W_WEEKEND.indexOf(imie) > -1
  };
}

/** Start pracy teraz (albo o podanej godzinie). Zapisuje od razu. */
function startPracy(k, p) {
  const o = kto_(k);
  p = p || {};
  const imie = o.imie;
  if (CONFIG.OSOBY.indexOf(imie) === -1) throw new Error('To konto nie prowadzi własnej ewidencji.');
  const dzis = dzisStr_();
  const start = p.start ? normalizujCzas_(p.start) : terazStr_().slice(11);
  if (!start) throw new Error('Zła godzina startu.');
  if (start > terazStr_().slice(11)) throw new Error('Godzina startu jest w przyszłości.');
  const miejsce = String(p.lokalizacja || '').trim().slice(0, 60);
  if (!miejsce) throw new Error('Wybierz miejsce pracy.');

  return zLockiem_(function () {
    const istn = znajdzWpis_(dzis, imie);
    if (istn) {
      const t = String(istn.r[KOL.TYP]);
      if (t !== 'Praca') throw new Error('Na dziś jest zapisane: ' + t + '. Usuń to najpierw w widoku miesiąca.');
      if (istn.r[KOL.KONIEC]) throw new Error('Dzisiejszy dzień jest już zakończony. Użyj „Popraw godziny”.');
      throw new Error('Dzień już trwa od ' + istn.r[KOL.START] + '.');
    }
    const w = pustyWiersz_(dzis, imie, 'Praca', o.imie);
    w[KOL.START] = start; w[KOL.MIEJSCE] = miejsce;
    w[KOL.UWAGI] = String(p.uwagi || '').trim().slice(0, 200);
    arkuszWpisow_().appendRow(w);
    log_(o.imie, 'start', dzis, imie, start + ' ' + miejsce);
    return stanDniaOsoby_(imie);
  });
}

function przerwaStart(k) {
  const o = kto_(k);
  return zLockiem_(function () {
    const istn = otwartyDzien_(o.imie);
    const prz = przerwy_(istn.r);
    if (prz.otwarta) throw new Error('Przerwa już trwa od ' + prz.otwarta + '.');
    const teraz = terazStr_().slice(11);
    prz.lista.push({ od: teraz, do: '' });
    zapiszPrzerwy_(istn, prz.lista);
    log_(o.imie, 'przerwa start', String(istn.r[KOL.DATA]), o.imie, teraz);
    return stanDniaOsoby_(o.imie);
  });
}

function przerwaStop(k) {
  const o = kto_(k);
  return zLockiem_(function () {
    const istn = otwartyDzien_(o.imie);
    const prz = przerwy_(istn.r);
    if (!prz.otwarta) throw new Error('Nie ma trwającej przerwy.');
    const teraz = terazStr_().slice(11);
    prz.lista[prz.lista.length - 1].do = teraz;
    zapiszPrzerwy_(istn, prz.lista);
    log_(o.imie, 'przerwa stop', String(istn.r[KOL.DATA]), o.imie, teraz);
    return stanDniaOsoby_(o.imie);
  });
}

/** Zakończ pracę teraz (albo o podanej godzinie). Zamyka dzisiejszy albo niezamknięty wczorajszy dzień. */
function koniecPracy(k, p) {
  const o = kto_(k);
  p = p || {};
  return zLockiem_(function () {
    const istn = otwartyDzien_(o.imie);
    const koniec = p.koniec ? normalizujCzas_(p.koniec) : terazStr_().slice(11);
    if (!koniec) throw new Error('Zła godzina zakończenia.');
    const prz = przerwy_(istn.r);
    if (prz.otwarta) prz.lista[prz.lista.length - 1].do = koniec;     // trwająca przerwa kończy się razem z dniem
    const w = istn.r.slice();
    w[KOL.KONIEC] = koniec;
    w[KOL.PRZ_OD] = prz.lista.map(function (x) { return x.od; }).join(', ');
    w[KOL.PRZ_DO] = prz.lista.map(function (x) { return x.do; }).join(', ');
    if (p.uwagi !== undefined) w[KOL.UWAGI] = String(p.uwagi || '').trim().slice(0, 200);
    const g = policzGodziny_(w);
    if (g.blad) throw new Error(g.blad);
    if (g.godziny > CONFIG.MAX_GODZIN_DOBA && !p.potwierdz) {
      return { pytanie: 'Wychodzi ' + fmtHM_(g.godziny) + '. Na pewno zakończyć o ' + koniec + '?', kod: 'DLUGI' };
    }
    w[KOL.GODZINY] = zKarmieniem_(w, g.godziny);
    w[KOL.ZAPISANO] = terazStr_();
    w[KOL.ZAPISAL] = o.imie;
    arkuszWpisow_().getRange(istn.wiersz, 1, 1, w.length).setValues([w]);
    log_(o.imie, 'koniec', String(w[KOL.DATA]), o.imie, opisWpisu_(w));
    odswiezKarty_([String(w[KOL.DATA]).slice(0, 7)]);
    return stanDniaOsoby_(o.imie);
  });
}

/**
 * Ręczna poprawka dnia (start, koniec, przerwy, miejsce, uwagi). Tworzy wpis, gdy go nie było.
 * Pracownik może poprawiać tylko dzisiejszy dzień. Wyjątek: osoby z PRACA_W_WEEKEND mogą podać p.data
 * z soboty / niedzieli / święta do WEEKEND_DNI_WSTECZ dni wstecz (praca w delegacji).
 */
function poprawDzis(k, p) {
  const o = kto_(k);
  p = p || {};
  const imie = o.imie;
  if (CONFIG.OSOBY.indexOf(imie) === -1) throw new Error('To konto nie prowadzi własnej ewidencji.');
  const dzis = dzisStr_();
  const data = p.data ? String(p.data) : dzis;
  if (data !== dzis) sprawdzDzienWeekendowy_(imie, data);
  return zLockiem_(function () {
    const istn = znajdzWpis_(data, imie);
    if (istn && String(istn.r[KOL.TYP]) !== 'Praca') throw new Error('Na ' + data + ' jest zapisane: ' + istn.r[KOL.TYP] + '. Usuń to najpierw.');
    if (istn && data !== dzis && !p.zastap) {
      return { pytanie: 'Na ' + data + ' jest już wpis (' + opisWpisu_(istn.r) + '). Zastąpić?', kod: 'ISTNIEJE' };
    }
    const w = istn ? istn.r.slice() : pustyWiersz_(data, imie, 'Praca', o.imie);
    zastosujPola_(w, p, true);
    const g = policzGodziny_(w);
    if (g.blad) throw new Error(g.blad);
    if (w[KOL.START] && w[KOL.KONIEC] && g.godziny > CONFIG.MAX_GODZIN_DOBA && !p.potwierdz) {
      return { pytanie: 'Wychodzi ' + fmtHM_(g.godziny) + ' w jednej dobie. Zapisać?', kod: 'DLUGI' };
    }
    w[KOL.GODZINY] = zKarmieniem_(w, g.godziny);
    w[KOL.ZAPISANO] = terazStr_();
    w[KOL.ZAPISAL] = o.imie;
    if (istn) arkuszWpisow_().getRange(istn.wiersz, 1, 1, w.length).setValues([w]);
    else arkuszWpisow_().appendRow(w);
    log_(o.imie, istn ? 'poprawka' : 'zapis ręczny', data, imie, opisWpisu_(w));
    odswiezKarty_([data.slice(0, 7)]);
    return stanDniaOsoby_(imie);
  });
}

/** Sobota / niedziela / święto, nie w przyszłości, nie starsze niż WEEKEND_DNI_WSTECZ — tylko dla PRACA_W_WEEKEND. */
function sprawdzDzienWeekendowy_(imie, data) {
  if (!dataOk_(data)) throw new Error('Zła data.');
  if (CONFIG.PRACA_W_WEEKEND.indexOf(imie) === -1) throw new Error('Można poprawiać tylko dzisiejszy dzień. Starsze zmienia administrator.');
  const dzis = dzisStr_();
  if (data > dzis) throw new Error('Nie można wpisać pracy z przyszłości.');
  if (dzienRoboczy_(data)) throw new Error('Wstecz można dopisać tylko sobotę, niedzielę albo święto. Dni robocze poprawia administrator.');
  if (data < dodajDni_(dzis, -CONFIG.WEEKEND_DNI_WSTECZ)) throw new Error('Najdalej ' + CONFIG.WEEKEND_DNI_WSTECZ + ' dni wstecz. Starsze zgłoś administratorowi.');
}

/** Przerwa na karmienie: dolicza do godzin faktycznych i zapisuje znacznik w Uwagach. */
function zKarmieniem_(w, godzinyFaktyczne) {
  const uwagi = String(w[KOL.UWAGI] || '').replace(/\s*·?\s*karmienie \+[\d,.]+ h/g, '').replace(/^\s*·\s*/, '').trim();
  w[KOL.UWAGI] = uwagi;
  if (CONFIG.PRZERWA_KARMIENIE.indexOf(String(w[KOL.IMIE])) === -1 || !godzinyFaktyczne) return godzinyFaktyczne;
  let kredyt = 0;
  if (godzinyFaktyczne > 6) kredyt = 1;
  else if (godzinyFaktyczne >= 4) kredyt = 0.5;
  if (!kredyt) return godzinyFaktyczne;
  w[KOL.UWAGI] = (uwagi ? uwagi + ' · ' : '') + 'karmienie +' + String(kredyt).replace('.', ',') + ' h';
  return zaokr_(godzinyFaktyczne + kredyt);
}

/** Pracownik usuwa tylko dzisiejszy wpis (np. przypadkowy Start). Admin — dowolny. */
function usunWpis(k, data, imieOpc) {
  const o = kto_(k);
  const imie = (o.admin && imieOpc) ? String(imieOpc).trim() : o.imie;
  data = String(data || '');
  if (!dataOk_(data)) throw new Error('Zła data.');
  if (!o.admin && data !== dzisStr_()) {
    try { sprawdzDzienWeekendowy_(imie, data); }
    catch (e) { throw new Error('Można usunąć tylko dzisiejszy wpis. Starsze poprawia administrator.'); }
  }
  return zLockiem_(function () {
    const istn = znajdzWpis_(data, imie);
    if (!istn) throw new Error('Nie ma takiego wpisu.');
    arkuszWpisow_().deleteRow(istn.wiersz);
    log_(o.imie, 'usunięcie', data, imie, opisWpisu_(istn.r));
    odswiezKarty_([data.slice(0, 7)]);
    return { ok: true, data: data, imie: imie };
  });
}

/* ------------------------------------------------------------------ */
/* NIEOBECNOŚCI ZAKRESEM                                               */
/* ------------------------------------------------------------------ */

/** Urlop / L4 od–do. Tylko dni robocze. Dni, które już mają wpis, są pomijane i zwracane. */
function zapiszNieobecnosc(k, p) {
  const o = kto_(k);
  p = p || {};
  const imie = (o.admin && p.imie) ? String(p.imie).trim() : o.imie;
  if (CONFIG.OSOBY.indexOf(imie) === -1) throw new Error('„' + imie + '” nie jest na liście pracowników.');
  const typ = String(p.typ || '');
  if (!CONFIG.RODZAJE[typ]) throw new Error('Wybierz typ nieobecności.');
  if (typ === 'Wolne' && !o.admin && CONFIG.PRACA_W_WEEKEND.indexOf(imie) === -1) {
    throw new Error('„Wolne” jest dla osób pracujących w weekendy. Odbiór godzin zgłoś administratorowi.');
  }
  const rodzaj = String(p.rodzaj || '').trim();
  if (rodzaj && CONFIG.RODZAJE[typ].indexOf(rodzaj) === -1) throw new Error('Nieznany rodzaj: ' + rodzaj);
  if (typ === 'Inne' && !String(p.uwagi || '').trim()) throw new Error('Przy „Inne” wpisz powód (np. oddanie krwi, opieka nad dzieckiem), bo księgowość musi go widzieć.');
  const od = String(p.od || ''), doD = String(p.do || od);
  if (!dataOk_(od) || !dataOk_(doD)) throw new Error('Podaj dzień „od” i „do”.');
  if (doD < od) throw new Error('Dzień „do” jest przed dniem „od”.');
  const dzis = dzisStr_();
  if (!o.admin) {
    if (od < dodajDni_(dzis, -CONFIG.NIEOBECNOSC_DNI_WSTECZ)) throw new Error('Najdalej ' + CONFIG.NIEOBECNOSC_DNI_WSTECZ + ' dni wstecz. Starsze zgłoś administratorowi.');
    if (doD > dodajDni_(dzis, CONFIG.NIEOBECNOSC_DNI_NAPRZOD)) throw new Error('Najdalej ' + CONFIG.NIEOBECNOSC_DNI_NAPRZOD + ' dni naprzód.');
  }
  const dni = dniMiedzy_(od, doD);
  if (dni.length > 92) throw new Error('Najwyżej 3 miesiące na raz.');
  const uwagi = [rodzaj, String(p.uwagi || '').trim()].filter(Boolean).join(' · ').slice(0, 200);

  return zLockiem_(function () {
    const zajete = {};
    wszystkieWpisy_().forEach(function (x) { if (String(x.r[KOL.IMIE]) === imie) zajete[String(x.r[KOL.DATA])] = true; });
    const sh = arkuszWpisow_();
    const zapisane = [], pominiete = [], miesiace = [];
    dni.forEach(function (d) {
      if (!dzienRoboczy_(d)) return;
      if (zajete[d]) { pominiete.push(d); return; }
      const w = pustyWiersz_(d, imie, typ, o.imie);
      w[KOL.UWAGI] = uwagi;
      sh.appendRow(w);
      zapisane.push(d);
      if (miesiace.indexOf(d.slice(0, 7)) === -1) miesiace.push(d.slice(0, 7));
    });
    if (zapisane.length) log_(o.imie, typ + (rodzaj ? ' (' + rodzaj + ')' : ''), od + '…' + doD, imie, zapisane.length + ' dni');
    odswiezKarty_(miesiace);
    return { ok: true, zapisane: zapisane, pominiete: pominiete, typ: typ, imie: imie };
  });
}

/* ------------------------------------------------------------------ */
/* ADMIN: WPIS RĘCZNY ZA KOGOŚ (dowolna data)                          */
/* ------------------------------------------------------------------ */

function zapiszZaKogos(k, p) {
  const o = admin_(k);
  p = p || {};
  const imie = String(p.imie || '').trim();
  if (CONFIG.OSOBY.indexOf(imie) === -1) throw new Error('Wybierz pracownika.');
  const data = String(p.data || '');
  if (!dataOk_(data)) throw new Error('Wybierz dzień.');
  const typ = String(p.typ || 'Praca');
  if (TYPY.indexOf(typ) === -1) throw new Error('Nieznany typ dnia.');
  return zLockiem_(function () {
    const istn = znajdzWpis_(data, imie);
    if (istn && !p.zastap) return { pytanie: 'Jest już wpis z ' + data + ' (' + opisWpisu_(istn.r) + '). Zastąpić?', kod: 'ISTNIEJE' };
    const w = pustyWiersz_(data, imie, typ, o.imie + ' (admin)');
    if (typ === 'Praca') {
      zastosujPola_(w, p, false);
      const g = policzGodziny_(w);
      if (g.blad) throw new Error(g.blad);
      if (!w[KOL.START] || !w[KOL.KONIEC]) throw new Error('Podaj start i koniec.');
      if (g.godziny > CONFIG.MAX_GODZIN_DOBA && !p.potwierdz) return { pytanie: 'Wychodzi ' + fmtHM_(g.godziny) + '. Zapisać?', kod: 'DLUGI' };
      w[KOL.GODZINY] = zKarmieniem_(w, g.godziny);
    } else {
      const rodzaj = String(p.rodzaj || '').trim();
      w[KOL.UWAGI] = [rodzaj, String(p.uwagi || '').trim()].filter(Boolean).join(' · ').slice(0, 200);
      if (typ === 'Inne' && !w[KOL.UWAGI]) throw new Error('Przy „Inne” wpisz powód w uwagach.');
    }
    if (istn) arkuszWpisow_().getRange(istn.wiersz, 1, 1, w.length).setValues([w]);
    else arkuszWpisow_().appendRow(w);
    log_(o.imie, istn ? 'poprawka (admin)' : 'zapis (admin)', data, imie, opisWpisu_(w));
    odswiezKarty_([data.slice(0, 7)]);
    return { ok: true, data: data, imie: imie, godziny: w[KOL.GODZINY], typ: typ };
  });
}

/* --- wspólne dla zapisu --- */

function pustyWiersz_(data, imie, typ, zapisal) {
  return [terazStr_(), data, imie, typ, '', '', '', '', '', 0, '', zapisal];
}

/** Nakłada pola z formularza (start, koniec, przerwy[], lokalizacja, uwagi) na wiersz. */
function zastosujPola_(w, p, tylkoPodane) {
  const ma = function (n) { return !tylkoPodane || p[n] !== undefined; };
  if (ma('start')) { w[KOL.START] = p.start ? normalizujCzas_(p.start) : ''; if (p.start && !w[KOL.START]) throw new Error('Zła godzina startu.'); }
  if (ma('koniec')) { w[KOL.KONIEC] = p.koniec ? normalizujCzas_(p.koniec) : ''; if (p.koniec && !w[KOL.KONIEC]) throw new Error('Zła godzina zakończenia.'); }
  if (ma('przerwy')) {
    const lista = (p.przerwy || []).map(function (x) {
      const od = normalizujCzas_(x && x.od), doG = normalizujCzas_(x && x.do);
      if (!od && !doG) return null;
      if (!od || !doG) throw new Error('Przerwa: uzupełnij obie godziny albo usuń przerwę.');
      return { od: od, do: doG };
    }).filter(Boolean);
    w[KOL.PRZ_OD] = lista.map(function (x) { return x.od; }).join(', ');
    w[KOL.PRZ_DO] = lista.map(function (x) { return x.do; }).join(', ');
  }
  if (ma('lokalizacja')) w[KOL.MIEJSCE] = String(p.lokalizacja || '').trim().slice(0, 60);
  if (ma('uwagi')) w[KOL.UWAGI] = String(p.uwagi || '').trim().slice(0, 200);
  if (w[KOL.START] && !w[KOL.MIEJSCE]) throw new Error('Wybierz miejsce pracy.');
  if (w[KOL.KONIEC] && !w[KOL.START]) throw new Error('Jest koniec bez startu. Uzupełnij godzinę startu.');
}

/**
 * Liczy godziny z wiersza (start, koniec, lista przerw). Zwraca {godziny, faktyczne, blad}.
 * Przerwy są przycinane do dnia pracy (co wystaje poza start–koniec, nie liczy się), zerowe i nakładające
 * się fragmenty są pomijane. Wynik "godziny" jest zaokrąglony wg CONFIG.ZAOKRAGLANIE_*, "faktyczne" co do minuty.
 */
function policzGodziny_(w) {
  const start = w[KOL.START], koniec = w[KOL.KONIEC];
  if (!start || !koniec) return { godziny: 0, faktyczne: 0, blad: '' };
  const dlugosc = roznicaMin_(start, koniec);
  const prz = przerwy_(w);
  if (prz.otwarta) return { godziny: 0, faktyczne: 0, blad: 'Przerwa od ' + prz.otwarta + ' nie ma godziny zakończenia.' };
  const minutyPrzerw = minutyPrzerw_(start, dlugosc, prz.lista);
  const netto = Math.max(0, dlugosc - minutyPrzerw);
  return { godziny: zaokr_(zaokraglijMinuty_(netto) / 60), faktyczne: zaokr_(netto / 60), blad: '' };
}

/** Suma minut przerw po przycięciu do okna [start, start+dlugosc] i po usunięciu nakładek. */
function minutyPrzerw_(start, dlugosc, lista) {
  const s0 = naMinuty_(start);
  const odcinki = (lista || []).map(function (x) {
    if (!x.od || !x.do) return null;
    let a = (naMinuty_(x.od) - s0 + 1440) % 1440, b = (naMinuty_(x.do) - s0 + 1440) % 1440;
    if (b < a) b = dlugosc;                      // przerwa "przez północ" względem startu: do końca dnia
    a = Math.max(0, Math.min(a, dlugosc)); b = Math.max(0, Math.min(b, dlugosc));
    return b > a ? [a, b] : null;
  }).filter(Boolean).sort(function (x, y) { return x[0] - y[0]; });
  let suma = 0, koniec = -1;
  odcinki.forEach(function (o) {
    const a = Math.max(o[0], koniec), b = o[1];
    if (b > a) { suma += b - a; koniec = b; }
  });
  return suma;
}

/** Zaokrąglenie minut do kroku z CONFIG: reszta < W_GORE_OD w dół, inaczej w górę. */
function zaokraglijMinuty_(min) {
  const krok = Number(CONFIG.ZAOKRAGLANIE_MIN) || 0;
  if (krok <= 1) return min;
  const reszta = min % krok;
  const baza = min - reszta;
  return reszta >= (Number(CONFIG.ZAOKRAGLANIE_W_GORE_OD) || Math.ceil(krok / 2)) ? baza + krok : baza;
}

/** Przerwy z kolumn G/H ("11:00, 14:00" / "11:15, 14:20"). Otwarta przerwa = od bez do. */
function przerwy_(r) {
  const od = String(r[KOL.PRZ_OD] || '').split(',').map(function (s) { return normalizujCzas_(s); }).filter(Boolean);
  const doG = String(r[KOL.PRZ_DO] || '').split(',').map(function (s) { return normalizujCzas_(s); }).filter(Boolean);
  const lista = od.map(function (o, i) { return { od: o, do: doG[i] || '' }; });
  const ost = lista[lista.length - 1];
  return { lista: lista, otwarta: (ost && !ost.do) ? ost.od : '' };
}

function zapiszPrzerwy_(istn, lista) {
  arkuszWpisow_().getRange(istn.wiersz, KOL.PRZ_OD + 1, 1, 2).setValues([[
    lista.map(function (x) { return x.od; }).join(', '),
    lista.map(function (x) { return x.do; }).join(', ')
  ]]);
}

/** Dzisiejszy albo wczorajszy niezamknięty dzień pracy osoby. */
function otwartyDzien_(imie) {
  const dzis = dzisStr_();
  const kandydaci = [dzis, dodajDni_(dzis, -1)];
  const lista = wszystkieWpisy_();
  for (let c = 0; c < kandydaci.length; c++) {
    for (let i = 0; i < lista.length; i++) {
      const r = lista[i].r;
      if (String(r[KOL.IMIE]) === imie && String(r[KOL.DATA]) === kandydaci[c] && String(r[KOL.TYP]) === 'Praca' && r[KOL.START] && !r[KOL.KONIEC]) {
        return lista[i];
      }
    }
  }
  throw new Error('Nie ma rozpoczętego dnia pracy. Kliknij Start.');
}

function znajdzWpis_(data, imie) {
  const lista = wszystkieWpisy_();
  for (let i = 0; i < lista.length; i++) {
    if (String(lista[i].r[KOL.DATA]) === data && String(lista[i].r[KOL.IMIE]) === imie) return lista[i];
  }
  return null;
}

function zLockiem_(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try { return fn(); } finally { lock.releaseLock(); }
}

function odswiezKarty_(miesiace) {
  if (!CONFIG.KARTA_PO_ZAPISIE) return;
  try {
    (miesiace || []).forEach(function (m) { zbudujKarteMiesiaca_(m, false); });
    if (miesiace && miesiace.length) zbudujKarteRazem_();
  } catch (e) { log_('system', 'błąd karty', (miesiace || []).join(','), '', String(e && e.message || e)); }
}

/* ------------------------------------------------------------------ */
/* ODCZYT: MÓJ MIESIĄC, ZESPÓŁ                                         */
/* ------------------------------------------------------------------ */

/** Miesiąc osoby: wszystkie dni, wpisy, norma, suma, urlop, L4, flagi. Admin może podać inne imię. */
function mojMiesiac(k, mies, imieOpc) {
  const o = kto_(k);
  const imie = (o.admin && imieOpc) ? String(imieOpc).trim() : o.imie;
  if (!/^\d{4}-\d{2}$/.test(String(mies || ''))) throw new Error('Zły miesiąc.');
  return miesiacOsoby_(imie, mies);
}

/**
 * Rozliczenie miesiąca osoby według normy dziennej (8 h × etat):
 *  - dzień pracy w dzień roboczy: do normy liczy się min(godziny, norma dzienna), nadwyżka idzie do nadgodzin,
 *    brak do normy dziennej to "luka";
 *  - praca w sobotę, niedzielę, święto: całość do nadgodzin;
 *  - Odbiór nadgodzin: luka wielkości normy dziennej (pokrywana z nadgodzin);
 *  - Urlop, L4, Inne, Wolne (NIEOBECNOSC_ZALICZANA): płatne, więc każdy dzień zalicza normę dzienną jak dzień
 *    pracy; norma miesiąca zostaje pełna. Typ spoza listy tylko obniża normę.
 * Luki pokrywane są z nadgodzin (pokryte = min(nadgodziny, luki)). Co zostało z nadgodzin = saldo nadgodzin.
 * doDnia: null = cały miesiąc (karta), data = stan "do dziś" (aplikacja w trakcie miesiąca).
 */
function rozlicz_(imie, rows, mies, doDnia, bankPrzed) {
  const bank = Math.max(0, Number(bankPrzed) || 0);
  const etat = CONFIG.ETATY[imie] || 1;
  const dn = zaokr_(8 * etat);
  const robocze = dniRoboczeMiesiaca_(mies);
  const roboczeDo = doDnia ? robocze.filter(function (d) { return d <= doDnia; }) : robocze;
  const norma = CONFIG.NORMA_WG_DNI_ROBOCZYCH
    ? roboczeDo.length * dn
    : CONFIG.NORMA_MIESIECZNA * etat * roboczeDo.length / Math.max(robocze.length, 1);
  const tygodniowo = (CONFIG.ROZLICZENIE_TYGODNIOWE || []).indexOf(imie) !== -1;
  const zaliczana = CONFIG.NIEOBECNOSC_ZALICZANA || [];
  let suma = 0, doNormy = 0, nad = 0, luki = 0, nieob = 0, obniza = 0;
  let tygodnie = null;
  if (tygodniowo) {
    tygodnie = rozliczTygodnie_(rows, mies, dn, roboczeDo, doDnia);
    tygodnie.forEach(function (t) {
      suma += t.godziny; doNormy += t.doNormy; nad += t.nadgodziny; luki += t.luka; nieob += t.nieobecnosci; obniza += t.obniza;
    });
  } else rows.forEach(function (r) {
    const d = String(r[KOL.DATA]);
    if (doDnia && d > doDnia) return;
    const typ = String(r[KOL.TYP]);
    const h = Number(r[KOL.GODZINY]) || 0;
    if (typ === 'Praca' || typ === 'Zdalnie') {
      suma += h;
      if (dzienRoboczy_(d)) {
        doNormy += Math.min(h, dn);
        nad += Math.max(h - dn, 0);
        if (r[KOL.KONIEC]) luki += Math.max(dn - h, 0);
      } else nad += h;
    } else if (typ === 'Odbiór nadgodzin') {
      luki += dn;
    } else if (zaliczana.indexOf(typ) !== -1 || typ === 'Chorobowe') {
      if (dzienRoboczy_(d)) nieob += dn;            // płatna nieobecność = zaliczona norma dzienna
    } else {
      obniza += dn;
    }
  });
  const pokryte = Math.min(bank + nad, luki);          // braki pokrywa najpierw bank z poprzednich miesięcy, potem nadwyżki
  const normaEff = Math.max(0, norma - obniza);
  const zaliczone = doNormy + nieob + pokryte;
  const zostalo = Math.max(0, normaEff - zaliczone);
  return {
    tryb: tygodniowo ? 'tydzien' : 'dzien', tygodnie: tygodnie, normaTygodniowa: zaokr_(dn * 5),
    etat: etat, normaDzienna: dn, norma: zaokr_(norma), normaPoNieobecnosciach: zaokr_(normaEff),
    nieobecnosciGodz: zaokr_(nieob), obnizenieNormy: zaokr_(obniza),
    suma: zaokr_(suma), razem: zaokr_(suma + nieob), zaliczone: zaokr_(zaliczone), zostalo: zaokr_(zostalo),
    nadgodzinyBrutto: zaokr_(nad), luki: zaokr_(luki), pokryte: zaokr_(pokryte),
    bankPrzed: zaokr_(bank), zmianaBanku: zaokr_(nad - pokryte),
    nadgodziny: zaokr_(bank + nad - pokryte), niedogodziny: zaokr_(zostalo)
  };
}

/**
 * Saldo banku nadgodzin na początek miesiąca: BANK_NADGODZIN_START + wynik każdego miesiąca od BANK_NADGODZIN_OD
 * do miesiąca poprzedzającego (pełne miesiące, bez cięcia do dziś). Przed BANK_NADGODZIN_OD zawsze 0.
 */
function bankPrzed_(imie, mies, rowsOsoby) {
  const od = CONFIG.BANK_NADGODZIN_OD;
  if (!od || !mies || mies < od) return 0;
  let saldo = Number((CONFIG.BANK_NADGODZIN_START || {})[imie]) || 0;
  for (let m = od; m < mies; m = nastepnyMiesiac_(m)) {
    const rm = rowsOsoby.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === m; });
    saldo = rozlicz_(imie, rm, m, null, saldo).nadgodziny;
  }
  return zaokr_(saldo);
}

function nastepnyMiesiac_(m) {
  const rok = Number(m.slice(0, 4)), nr = Number(m.slice(5, 7));
  return nr === 12 ? (rok + 1) + '-01' : rok + '-' + ('0' + (nr + 1)).slice(-2);
}

/**
 * Tryb tygodniowy: tygodnie pon–nd cięte na granicy miesiąca. Norma tygodnia = dni robocze tygodnia (w miesiącu,
 * do doDnia) × norma dzienna. Płatne nieobecności (Urlop, L4, Inne) zaliczają normę dzienną do sumy tygodnia.
 * Suma godzin pracy + zaliczonych nieobecności z całego tygodnia (także sobota/niedziela) porównywana z normą:
 * nadwyżka = nadgodziny, brak = luka. Luka liczona dopiero, gdy
 * tydzień się skończył (lub to ostatni dzień i dzień pracy zamknięty). "Wolne" w tym trybie nie zmienia normy
 * (godziny z weekendu już są w sumie tygodnia). "Odbiór nadgodzin" = luka wielkości normy dziennej.
 * Tydzień bez żadnego wpisu nie tworzy luki (najpewniej nic nie zalogowano), ale liczy się do normy miesiąca.
 */
function rozliczTygodnie_(rows, mies, dn, roboczeDo, doDnia) {
  const zaliczana = CONFIG.NIEOBECNOSC_ZALICZANA || [];
  const rok = Number(mies.slice(0, 4)), nr = Number(mies.slice(5, 7));
  const ile = new Date(rok, nr, 0).getDate();
  const ostatni = mies + '-' + ('0' + ile).slice(-2);
  const koniecOkresu = doDnia && doDnia < ostatni ? doDnia : ostatni;
  const poDacie = {};
  rows.forEach(function (r) { poDacie[String(r[KOL.DATA])] = r; });
  const tyg = {};
  const kolejnosc = [];
  const dodaj = function (d) {
    const pn = poniedzialek_(d);
    if (!tyg[pn]) { tyg[pn] = { od: d, do: d, godziny: 0, norma: 0, nieobecnosci: 0, obniza: 0, luka: 0, dniPracy: 0, wpisy: 0, otwartyDzien: false }; kolejnosc.push(pn); }
    const t = tyg[pn];
    if (d < t.od) t.od = d;
    if (d > t.do) t.do = d;
    return t;
  };
  for (let d = 1; d <= ile; d++) {
    const data = mies + '-' + ('0' + d).slice(-2);
    if (data > koniecOkresu) break;
    const t = dodaj(data);
    if (roboczeDo.indexOf(data) !== -1) t.norma += dn;
    const r = poDacie[data];
    if (!r) continue;
    t.wpisy++;
    const typ = String(r[KOL.TYP]);
    const h = Number(r[KOL.GODZINY]) || 0;
    if (typ === 'Praca' || typ === 'Zdalnie') {
      t.godziny += h; if (h > 0) t.dniPracy++;
      if (!r[KOL.KONIEC]) t.otwartyDzien = true;
    } else if (typ === 'Odbiór nadgodzin') t.luka += dn;
    else if (typ === 'Wolne') { /* w trybie tygodniowym neutralne: godziny z weekendu są już w sumie tygodnia */ }
    else if (zaliczana.indexOf(typ) !== -1 || typ === 'Chorobowe') { if (roboczeDo.indexOf(data) !== -1) t.nieobecnosci += dn; }
    else t.obniza += dn;
  }
  return kolejnosc.map(function (pn) {
    const t = tyg[pn];
    const normaEff = Math.max(0, t.norma - t.obniza);
    const razem = t.godziny + t.nieobecnosci;
    const koniecTyg = dodajDni_(pn, 6);
    const kon = koniecTyg < ostatni ? koniecTyg : ostatni;
    // tydzień bez żadnego wpisu (nic nie zalogowano) nie tworzy luki, tak jak dni bez wpisu w trybie dziennym
    const zamkniety = t.wpisy > 0 && (!doDnia || doDnia > kon || (doDnia === kon && !t.otwartyDzien));
    const nadgodziny = Math.max(0, razem - normaEff);
    const brak = Math.max(0, normaEff - razem);
    return {
      od: t.od, do: t.do, godziny: zaokr_(t.godziny), razem: zaokr_(razem), norma: zaokr_(t.norma), normaPoNieobecnosciach: zaokr_(normaEff),
      nieobecnosci: zaokr_(t.nieobecnosci), obniza: zaokr_(t.obniza), dniPracy: t.dniPracy, zamkniety: zamkniety,
      doNormy: zaokr_(Math.max(0, Math.min(razem, normaEff) - t.nieobecnosci)), nadgodziny: zaokr_(nadgodziny),
      luka: zaokr_(t.luka + (zamkniety ? brak : 0)), roznica: zaokr_(razem - normaEff)
    };
  });
}

/** Poniedziałek tygodnia, w którym jest data (RRRR-MM-DD). */
function poniedzialek_(dataStr) {
  const cz = dataStr.split('-');
  const dow = new Date(Number(cz[0]), Number(cz[1]) - 1, Number(cz[2])).getDay();
  return dodajDni_(dataStr, -((dow + 6) % 7));
}

/** Wymiar urlopu osoby w roku: wpis w URLOP_WYMIAR albo URLOP_ROCZNY × etat (w górę). */
function wymiarUrlopu_(imie) {
  if (CONFIG.URLOP_WYMIAR && CONFIG.URLOP_WYMIAR[imie] != null) return Number(CONFIG.URLOP_WYMIAR[imie]) || 0;
  return Math.ceil((Number(CONFIG.URLOP_ROCZNY) || 0) * (CONFIG.ETATY[imie] || 1));
}

/**
 * Urlop w roku. Każdy dzień urlopu (wpis "Urlop") zużywa normę dzienną osoby (8 h × etat). Pula:
 *  - z URLOP_STAN (stan przeniesiony: przysługuje / wykorzystane na dzień URLOP_STAN_NA, wpisy po tej dacie doliczane),
 *  - inaczej wymiar w dniach × 8 h (URLOP_WYMIAR / URLOP_ROCZNY × etat), liczone od wszystkich wpisów w roku.
 * Dni "osoby" = godziny / norma dzienna (pełny etat: 1 dzień = 8 h; 7/8: 7 h; 1/2: 4 h). rows = wpisy osoby (dowolne).
 */
function urlopRoczny_(imie, rok, rows) {
  const r = String(rok);
  const wszystkie = (rows || wszystkieWpisy_().map(function (x) { return x.r; }).filter(function (x) { return String(x[KOL.IMIE]) === imie; }));
  const dzis = dzisStr_();
  const etat = CONFIG.ETATY[imie] || 1;
  const dn = zaokr_(8 * etat);
  const stan = (CONFIG.URLOP_STAN || {})[imie];
  const stanNa = String(CONFIG.URLOP_STAN_NA || '');
  const zeStanu = !!(stan && stanNa.slice(0, 4) === r);
  const lista = wszystkie.filter(function (x) {
    const d = String(x[KOL.DATA]);
    return String(x[KOL.TYP]) === 'Urlop' && d.slice(0, 4) === r && (!zeStanu || d > stanNa);
  });
  const dniWpisow = lista.length;
  const dniZaplanowane = lista.filter(function (x) { return String(x[KOL.DATA]) > dzis; }).length;
  let przyslugujeGodz, bazaGodz = 0;
  if (zeStanu) {
    przyslugujeGodz = stan.przyslugujeGodz != null ? Number(stan.przyslugujeGodz) : (Number(stan.przysluguje) || 0) * 8;
    bazaGodz = stan.wykorzystaneGodz != null ? Number(stan.wykorzystaneGodz) : (Number(stan.wykorzystane) || 0) * 8;
  } else przyslugujeGodz = wymiarUrlopu_(imie) * 8;
  const wykorzystaneGodz = zaokr_(bazaGodz + dniWpisow * dn);
  const zostaloGodz = zaokr_(Math.max(0, przyslugujeGodz - wykorzystaneGodz));
  const dni = zaokr_(wykorzystaneGodz / dn), przyslugujeDni = zaokr_(przyslugujeGodz / dn), zostaloDni = zaokr_(zostaloGodz / dn);
  return {
    rok: Number(rok), godzinowo: etat !== 1, normaDzienna: dn, stanNa: zeStanu ? stanNa : '',
    // dni = godziny / norma dzienna osoby (mogą być ułamkowe), godziny = ile puli zużyto
    wykorzystane: dni, zaplanowane: dniZaplanowane, wykorzystaneGodz: wykorzystaneGodz, zaplanowaneGodz: zaokr_(dniZaplanowane * dn),
    przysluguje: przyslugujeDni, przyslugujeGodz: zaokr_(przyslugujeGodz),
    zostaloGodz: zostaloGodz, zostalo: zostaloDni, zostaloDni: zostaloDni,
    tekst: urlopTekst_(etat !== 1, wykorzystaneGodz, przyslugujeGodz, dni, przyslugujeDni)
  };
}

/** Dni z jednym miejscem po przecinku: 2.5 -> "2,5", 26 -> "26". */
function fmtDni_(x) { return String(Math.round((Number(x) || 0) * 10) / 10).replace('.', ','); }

/** Jeden zapis dla kart i PDF: pełny etat "20 z 24 dni", niepełny "120 h z 200 h (17,1 dni)". */
function urlopTekst_(godzinowo, wykGodz, przysGodz, dni, przysDni) {
  if (!godzinowo) return fmtDni_(dni) + ' z ' + fmtDni_(przysDni) + ' dni';
  return fmtHM_(wykGodz) + ' z ' + fmtHM_(przysGodz) + ' (' + fmtDni_(dni) + ' dni)';
}

function miesiacOsoby_(imie, mies) {
  const dzis = dzisStr_();
  const nazwa = MIESIACE_PL[Number(mies.slice(5, 7)) - 1] + ' ' + mies.slice(0, 4);
  if (CONFIG.OSOBY.indexOf(imie) === -1) {
    return { mies: mies, nazwa: nazwa, imie: imie, bezEwidencji: true, dni: [], wpisy: [], brakujace: [], etat: 1,
             norma: 0, normaDoDzis: 0, suma: 0, dniPracy: 0, zdalnie: 0, urlop: 0, l4: 0, wolne: 0, odbior: 0, inne: 0, bilans: 0, urlopRok: null };
  }
  const moje = wszystkieWpisy_().map(function (x) { return x.r; }).filter(function (r) { return String(r[KOL.IMIE]) === imie; });
  const rows = moje.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === mies; });
  const urlopRok = urlopRoczny_(imie, mies.slice(0, 4), moje);
  const poDacie = {};
  rows.forEach(function (r) { poDacie[String(r[KOL.DATA])] = wpisDoObiektu_(r); });

  const a = agreguj_(rows);
  const etat = CONFIG.ETATY[imie] || 1;
  const robocze = dniRoboczeMiesiaca_(mies);
  const roboczeDoDzis = robocze.filter(function (d) { return d <= dzis; });
  const norma = zaokr_(normaMiesiaca_(mies) * etat);
  const normaDoDzis = zaokr_(normaDoDzis_(mies, robocze, roboczeDoDzis) * etat);
  const biezacy = mies === dzis.slice(0, 7);
  const bank = bankPrzed_(imie, mies, moje);
  const roz = rozlicz_(imie, rows, mies, biezacy ? dzis : null, bank);
  const rozPelne = biezacy ? rozlicz_(imie, rows, mies, null, bank) : roz;

  const rok = Number(mies.slice(0, 4)), nr = Number(mies.slice(5, 7));
  const ile = new Date(rok, nr, 0).getDate();
  const dni = [];
  for (let d = 1; d <= ile; d++) {
    const data = mies + '-' + ('0' + d).slice(-2);
    const w = poDacie[data] || null;
    const roboczy = dzienRoboczy_(data);
    let status = 'wolny';
    if (w) status = w.typ === 'Praca' ? (w.koniec ? 'praca' : 'w toku') : (w.typ === 'Urlop' ? 'urlop' : (w.typ === 'Wolne' ? 'wolne-zamian' : (w.typ === 'Odbiór nadgodzin' ? 'odbior' : (w.typ === 'Inne' ? 'inne' : 'l4'))));
    else if (roboczy) status = data < dzis ? 'brak' : (data === dzis ? 'dzis' : 'przyszly');
    let roznica = null;
    if (roz.tryb !== 'tydzien') {
      if (w && w.typ === 'Praca' && w.koniec) roznica = zaokr_(roboczy ? w.godziny - roz.normaDzienna : w.godziny);
      if (w && w.typ === 'Odbiór nadgodzin') roznica = -roz.normaDzienna;
    }
    dni.push({ data: data, dzien: dzienTygodnia_(data), roboczy: roboczy, status: status, wpis: w, roznica: roznica });
  }
  const brakujace = dni.filter(function (x) { return x.status === 'brak'; }).map(function (x) { return x.data; });

  return {
    mies: mies, nazwa: nazwa, imie: imie, dzis: dzis, dni: dni, brakujace: brakujace, etat: etat,
    norma: norma, normaDoDzis: normaDoDzis, dniRobocze: robocze.length, dniRoboczeDoDzis: roboczeDoDzis.length,
    suma: zaokr_(a.godziny), dniPracy: a.dni, zdalnie: a.zdalnie, urlop: a.urlop, l4: a.l4, wolne: a.wolne, odbior: a.odbior, inne: a.inne,
    rozliczenie: roz, rozliczeniePelne: rozPelne, urlopRok: urlopRok,
    bilans: zaokr_(a.godziny - (mies < dzis.slice(0, 7) ? norma : normaDoDzis))
  };
}

/** Panel administratora: wszyscy pracownicy w danym miesiącu + stan dzisiejszy. */
function przegladZespolu(k, mies) {
  admin_(k);
  if (!/^\d{4}-\d{2}$/.test(String(mies || ''))) throw new Error('Zły miesiąc.');
  const dzis = dzisStr_();
  const wszystkie = wszystkieWpisy_().map(function (x) { return x.r; });
  const wMies = wszystkie.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === mies; });
  const robocze = dniRoboczeMiesiaca_(mies);
  const roboczeDoDzis = robocze.filter(function (d) { return d <= dzis; });
  const normaBaz = normaMiesiaca_(mies);
  const normaDoDzisBaz = normaDoDzis_(mies, robocze, roboczeDoDzis);
  const zamkniety = mies < dzis.slice(0, 7);

  const osoby = CONFIG.OSOBY.map(function (imie) {
    const moje = wMies.filter(function (r) { return String(r[KOL.IMIE]) === imie; });
    const a = agreguj_(moje);
    const etat = CONFIG.ETATY[imie] || 1;
    const maja = {};
    moje.forEach(function (r) { maja[String(r[KOL.DATA])] = true; });
    const brak = roboczeDoDzis.filter(function (d) { return d < dzis && !maja[d]; });
    const dzisR = wszystkie.filter(function (r) { return String(r[KOL.IMIE]) === imie && String(r[KOL.DATA]) === dzis; })[0];
    const odniesienie = (zamkniety ? normaBaz : normaDoDzisBaz) * etat;
    const wszystkieMoje = wszystkie.filter(function (r) { return String(r[KOL.IMIE]) === imie; });
    const roz = rozlicz_(imie, moje, mies, zamkniety ? null : dzis, bankPrzed_(imie, mies, wszystkieMoje));
    const urlopRok = urlopRoczny_(imie, mies.slice(0, 4), wszystkieMoje);
    return {
      imie: imie, etat: etat, urlopRok: urlopRok,
      godziny: zaokr_(a.godziny), norma: zaokr_(normaBaz * etat), normaDoDzis: zaokr_(normaDoDzisBaz * etat),
      bilans: zaokr_(a.godziny - odniesienie), rozliczenie: roz,
      dniPracy: a.dni, zdalnie: a.zdalnie, urlop: a.urlop, l4: a.l4, wolne: a.wolne, odbior: a.odbior, inne: a.inne,
      brakujace: brak, dzis: dzisR ? statusDzis_(dzisR) : ''
    };
  });

  return {
    mies: mies, nazwa: MIESIACE_PL[Number(mies.slice(5, 7)) - 1] + ' ' + mies.slice(0, 4),
    dzis: dzis, dzisRoboczy: dzienRoboczy_(dzis), zamkniety: zamkniety,
    dniRobocze: robocze.length, dniRoboczeDoDzis: roboczeDoDzis.length,
    norma: zaokr_(normaBaz), normaDoDzis: zaokr_(normaDoDzisBaz), osoby: osoby,
    arkuszUrl: 'https://docs.google.com/spreadsheets/d/' + CONFIG.SHEET_ID + '/edit'
  };
}

function statusDzis_(r) {
  const typ = String(r[KOL.TYP]);
  if (typ !== 'Praca') return typ;
  if (!r[KOL.KONIEC]) {
    const prz = przerwy_(r);
    return prz.otwarta ? 'przerwa od ' + prz.otwarta : 'w pracy od ' + r[KOL.START];
  }
  return r[KOL.START] + '–' + r[KOL.KONIEC] + ', ' + fmtHM_(Number(r[KOL.GODZINY]) || 0);
}

function przeliczKarte(k, mies) {
  admin_(k);
  if (!/^\d{4}-\d{2}$/.test(String(mies || ''))) throw new Error('Zły miesiąc.');
  zbudujKarteMiesiaca_(mies, false);
  zbudujKarteRazem_();
  return { ok: true };
}

/* ------------------------------------------------------------------ */
/* KARTA EWIDENCJI OSOBY (HTML do druku / PDF na Dysk)                 */
/* ------------------------------------------------------------------ */

function kartaHtml(k, mies, imieOpc) {
  const o = kto_(k);
  const imie = (o.admin && imieOpc) ? String(imieOpc).trim() : o.imie;
  if (!/^\d{4}-\d{2}$/.test(String(mies || ''))) throw new Error('Zły miesiąc.');
  return zbudujKarteHtml_(miesiacOsoby_(imie, mies));
}

/** Zapisuje kartę osoby jako PDF w podfolderze "Karty PDF" obok arkusza. Zwraca link. */
function zapiszKartePdf(k, mies, imieOpc) {
  const o = kto_(k);
  const imie = (o.admin && imieOpc) ? String(imieOpc).trim() : o.imie;
  if (!/^\d{4}-\d{2}$/.test(String(mies || ''))) throw new Error('Zły miesiąc.');
  const html = zbudujKarteHtml_(miesiacOsoby_(imie, mies));
  const pdf = Utilities.newBlob(html, 'text/html', 'karta.html').getAs('application/pdf');
  const nazwa = 'Ewidencja ' + mies + ' ' + imie + '.pdf';
  pdf.setName(nazwa);
  const plik = DriveApp.getFileById(CONFIG.SHEET_ID);
  const rodzice = plik.getParents();
  const folderArk = rodzice.hasNext() ? rodzice.next() : DriveApp.getRootFolder();
  const podf = folderArk.getFoldersByName('Karty PDF');
  const folder = podf.hasNext() ? podf.next() : folderArk.createFolder('Karty PDF');
  const stare = folder.getFilesByName(nazwa);
  while (stare.hasNext()) stare.next().setTrashed(true);
  const nowy = folder.createFile(pdf);
  log_(o.imie, 'PDF karty', mies, imie, nowy.getUrl());
  return { ok: true, url: nowy.getUrl(), nazwa: nazwa };
}

function zbudujKarteHtml_(m) {
  const esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  let wiersze = '';
  m.dni.forEach(function (d) {
    const w = d.wpis;
    const przerwa = w ? w.przerwy.map(function (x) { return x.od + '–' + x.do; }).join(', ') : '';
    const typ = w ? (w.typ === 'Praca' ? 'Praca' : '<b>' + esc(w.typ) + '</b>') : '';
    wiersze += '<tr' + (d.roboczy ? '' : ' class="wolny"') + '><td>' + d.data.slice(8) + '</td><td>' + d.dzien + '</td>' +
      '<td>' + typ + '</td><td>' + esc(w ? w.start : '') + '</td><td>' + esc(w ? w.koniec : '') + '</td>' +
      '<td>' + esc(przerwa) + '</td><td class="n">' + (w && w.godziny ? fmtHM_(w.godziny) : '') + '</td>' +
      '<td>' + esc(w ? w.lokalizacja : '') + '</td><td>' + esc(w ? w.uwagi : '') + '</td></tr>';
  });
  const rp = m.rozliczeniePelne || m.rozliczenie || { nadgodziny: 0, niedogodziny: 0 };
  const nad = rp.nadgodziny, nie = rp.niedogodziny;
  const pole = function (n, v) { return '<div><span>' + n + '</span><b>' + v + '</b></div>'; };

  return '<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><title>Ewidencja ' + esc(m.mies) + ' ' + esc(m.imie) + '</title>' +
    '<style>body{font:12px/1.35 Arial,Helvetica,sans-serif;color:#111;margin:24px}h1{font-size:18px;margin:0 0 2px}' +
    'h2{font-size:13px;font-weight:normal;color:#555;margin:0 0 14px}table{border-collapse:collapse;width:100%}' +
    'th,td{border:1px solid #999;padding:4px 6px;text-align:left}th{background:#eee}td.n{text-align:right}' +
    'tr.wolny td{background:#f3f3f3;color:#777}.pods{margin-top:14px;display:flex;gap:24px;flex-wrap:wrap}' +
    '.pods div span{display:block;font-size:10px;color:#555;text-transform:uppercase}.pods div b{font-size:15px}' +
    '.podpisy{margin-top:40px;display:flex;justify-content:space-between}.podpisy div{width:40%;border-top:1px solid #333;padding-top:4px;font-size:11px;color:#555}' +
    '@media print{body{margin:10mm}}</style></head><body>' +
    '<h1>Ewidencja czasu pracy — ' + esc(m.nazwa) + '</h1>' +
    '<h2>' + esc(m.imie) + ' &nbsp;·&nbsp; etat ' + etatTekst_(m.etat) + ' &nbsp;·&nbsp; Fundacja Redemptoris Missio &nbsp;·&nbsp; wydruk ' + terazStr_() + '</h2>' +
    '<table><tr><th>Dz.</th><th>Tyg.</th><th>Typ</th><th>Start</th><th>Koniec</th><th>Przerwy</th><th>Godz.</th><th>Miejsce</th><th>Uwagi</th></tr>' +
    wiersze + '</table>' +
    '<div class="pods">' + pole('Przepracowane', fmtHM_(m.suma)) + pole('Urlop i inne płatne', fmtHM_(rp.nieobecnosciGodz || 0)) +
    pole('Razem zaliczone', fmtHM_(rp.zaliczone || 0)) + pole('Norma', fmtHM_(m.norma)) +
    (rp.bankPrzed > 0 ? pole('Bank nadg. na start', fmtHM_(rp.bankPrzed)) : '') + pole(rp.bankPrzed > 0 ? 'Nadgodziny (bank)' : 'Nadgodziny', fmtHM_(nad)) + pole('Niedogodziny', fmtHM_(nie)) + pole('Dni pracy', m.dniPracy) +
    pole('w tym HO', m.zdalnie) + pole('Urlop', m.urlop) + pole('Urlop w roku ' + esc(m.mies.slice(0, 4)), m.urlopRok ? esc(m.urlopRok.tekst) : '') + pole('L4', m.l4) + pole('Wolne', m.wolne) + pole('Odbiór nadg.', m.odbior) + pole('Inne', m.inne) + '</div>' +
    '<div class="podpisy"><div>podpis pracownika</div><div>podpis pracodawcy</div></div>' +
    '</body></html>';
}

/* ------------------------------------------------------------------ */
/* KARTA MIESIĄCA W ARKUSZU                                            */
/* ------------------------------------------------------------------ */

// Nadgodziny = nadwyżka ponad normę dzienną (po pokryciu krótszych dni i odbiorów). Niedogodziny = czego brakuje
// do normy miesiąca po odjęciu nieobecności (urlop, L4, inne, wolne obniżają normę).
// Godziny = faktycznie przepracowane; Płatne nieobecn. = urlop, L4, inne, wolne liczone po normie dziennej;
// Razem zaliczone = jedno i drugie plus luki pokryte z banku nadgodzin. To "Razem" porównuje się z normą.
const NAGL_SUM = ['Imię', 'Etat', 'Dni pracy', 'w tym HO', 'Godziny', 'Płatne nieobecn. (godz.)', 'Razem zaliczone', 'Norma', 'Nadgodziny', 'Niedogodziny',
                  'Urlop (dni)', 'Urlop w roku', 'L4 (dni)', 'Wolne (dni)', 'Odbiór nadg. (dni)', 'Inne (dni)'];

function etatTekst_(etat) {
  if (etat === 1) return '1';
  if (etat === 0.5) return '1/2';
  if (etat === 0.75) return '3/4';
  if (etat === 0.875) return '7/8';
  if (etat === 0.25) return '1/4';
  return String(etat).replace('.', ',');
}

function wierszPodsumowania_(imie, rows, normaBazowa, mies, rowsOsoby) {
  const a = agreguj_(rows);
  const etat = CONFIG.ETATY[imie] || 1;
  const wszystkieMoje = rowsOsoby || wszystkieWpisy_().map(function (x) { return x.r; }).filter(function (r) { return String(r[KOL.IMIE]) === imie; });
  const roz = rozlicz_(imie, rows, mies, null, bankPrzed_(imie, mies, wszystkieMoje));
  const u = urlopRoczny_(imie, mies.slice(0, 4), wszystkieMoje);
  return [imie, etatTekst_(etat), a.dni, a.zdalnie, dur_(a.godziny), dur_(roz.nieobecnosciGodz), dur_(roz.zaliczone), dur_(roz.norma), dur_(roz.nadgodziny), dur_(roz.niedogodziny),
          a.urlop, u.tekst, a.l4, a.wolne, a.odbior, a.inne];
}

function zbudujKarteMiesiaca_(mies, aktywuj) {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  const wszystkieRows = wszystkieWpisy_().map(function (x) { return x.r; });
  const wpisy = wszystkieRows.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === mies; });
  wpisy.sort(function (a, b) {
    if (String(a[KOL.DATA]) !== String(b[KOL.DATA])) return String(a[KOL.DATA]) < String(b[KOL.DATA]) ? -1 : 1;
    return String(a[KOL.IMIE]) < String(b[KOL.IMIE]) ? -1 : 1;
  });

  const agg = {};
  const kolejnosc = CONFIG.OSOBY.slice();
  kolejnosc.forEach(function (o) { agg[o] = []; });
  wpisy.forEach(function (r) {
    const imie = String(r[KOL.IMIE]);
    if (!agg[imie]) { agg[imie] = []; kolejnosc.push(imie); }
    agg[imie].push(r);
  });

  const normaBazowa = normaMiesiaca_(mies);
  const dzis = dzisStr_();
  const biezacy = mies === dzis.slice(0, 7);
  const robocze = dniRoboczeMiesiaca_(mies);
  const roboczeDoDzis = robocze.filter(function (d) { return d <= dzis; });

  let sh = ss.getSheetByName(mies);
  if (!sh) sh = ss.insertSheet(mies);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.clear();
  sh.clearConditionalFormatRules();

  const rok = Number(mies.slice(0, 4)), nrMies = Number(mies.slice(5, 7));
  sh.getRange('A1').setValue(MIESIACE_PL[nrMies - 1] + ' ' + rok).setFontSize(16).setFontWeight('bold');
  sh.getRange('A2').setValue(
    'Norma: ' + fmtHM_(normaBazowa) + ' ' + (CONFIG.NORMA_WG_DNI_ROBOCZYCH ? '(z kalendarza, ' + robocze.length + ' dni roboczych)' : '(stała)') +
    (biezacy ? '   ·   norma do dziś: ' + fmtHM_(normaDoDzis_(mies, robocze, roboczeDoDzis)) : '') +
    '   ·   odświeżono ' + Utilities.formatDate(new Date(), CONFIG.STREFA, 'd.MM.yyyy HH:mm')
  ).setFontColor('#6B7A85');

  const wierszNagl = 4;
  sh.getRange(wierszNagl, 1, 1, NAGL_SUM.length).setValues([NAGL_SUM])
    .setFontWeight('bold').setBackground('#11202B').setFontColor('#FFFFFF');

  const wiersze = kolejnosc.map(function (imie) {
    return wierszPodsumowania_(imie, agg[imie], normaBazowa, mies, wszystkieRows.filter(function (r) { return String(r[KOL.IMIE]) === imie; }));
  });
  if (wiersze.length) {
    sh.getRange(wierszNagl + 1, 1, wiersze.length, NAGL_SUM.length).setValues(wiersze);
    const razem = wierszNagl + 1 + wiersze.length;
    const sum = function (i) { return wiersze.reduce(function (s, w) { return s + (Number(w[i]) || 0); }, 0); };
    sh.getRange(razem, 1, 1, NAGL_SUM.length).setValues([[
      'RAZEM', '', sum(2), sum(3), sum(4), sum(5), sum(6), sum(7), sum(8), sum(9), sum(10), '', sum(12), sum(13), sum(14), sum(15)
    ]]).setFontWeight('bold').setBorder(true, null, null, null, null, null);
    sh.getRange(wierszNagl + 1, 9, wiersze.length + 1, 1).setFontColor('#0B6E4F');
    sh.getRange(wierszNagl + 1, 10, wiersze.length + 1, 1).setFontColor('#C2410C');
    sh.getRange(wierszNagl + 1, 5, wiersze.length + 1, 6).setNumberFormat(FORMAT_GODZIN);
  }

  const startSzcz = wierszNagl + wiersze.length + 4;
  sh.getRange(startSzcz - 1, 1)
    .setValue('Szczegóły — kliknij ikonę lejka w nagłówku, żeby filtrować po osobie lub dacie')
    .setFontColor('#6B7A85');
  const naglSzcz = ['Data', 'Dzień', 'Imię', 'Typ', 'Start', 'Koniec', 'Przerwy', 'Miejsce', 'Godziny', 'Uwagi'];
  sh.getRange(startSzcz, 1, 1, naglSzcz.length).setValues([naglSzcz])
    .setFontWeight('bold').setBackground('#11202B').setFontColor('#FFFFFF');

  if (wpisy.length) {
    const szcz = wpisy.map(function (r) {
      const d = String(r[KOL.DATA]);
      const prz = przerwy_(r).lista.map(function (x) { return x.od + '–' + (x.do || '…'); }).join(', ');
      const koniec = (String(r[KOL.TYP]) === 'Praca' && r[KOL.START] && !r[KOL.KONIEC]) ? 'w toku' : String(r[KOL.KONIEC]);
      return [d, dzienTygodnia_(d), String(r[KOL.IMIE]), String(r[KOL.TYP]), String(r[KOL.START]), koniec,
              prz, String(r[KOL.MIEJSCE]), dur_(r[KOL.GODZINY]), String(r[KOL.UWAGI])];
    });
    sh.getRange(startSzcz + 1, 1, szcz.length, naglSzcz.length).setValues(szcz);
    sh.getRange(startSzcz + 1, 9, szcz.length, 1).setNumberFormat(FORMAT_GODZIN);
    sh.getRange(startSzcz, 1, szcz.length + 1, naglSzcz.length).createFilter();
  }

  sh.setColumnWidth(1, 110); sh.setColumnWidth(2, 95); sh.setColumnWidth(3, 110);
  for (let c = 4; c <= 13; c++) sh.setColumnWidth(c, 105);
  sh.setHiddenGridlines(true);
  if (aktywuj) ss.setActiveSheet(sh);
  return sh;
}

/** Karta "Razem" — pierwsza zakładka: suma wszystkich miesięcy per osoba + macierz miesiąc × osoba. */
function zbudujKarteRazem_() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  const wszystkie = wszystkieWpisy_().map(function (x) { return x.r; });
  const miesiace = miesiaceZWpisami_();
  const osoby = CONFIG.OSOBY.slice();
  wszystkie.forEach(function (r) { const i = String(r[KOL.IMIE]); if (osoby.indexOf(i) === -1) osoby.push(i); });
  const dzis = dzisStr_(), dzisM = dzis.slice(0, 7);
  const normaM = function (m) {
    if (m !== dzisM) return normaMiesiaca_(m);
    const rb = dniRoboczeMiesiaca_(m);
    return normaDoDzis_(m, rb, rb.filter(function (d) { return d <= dzis; }));
  };

  let sh = ss.getSheetByName(CONFIG.ARKUSZ_RAZEM);
  if (!sh) sh = ss.insertSheet(CONFIG.ARKUSZ_RAZEM, 0);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.clear();

  sh.getRange('A1').setValue('Razem — wszystkie miesiące').setFontSize(16).setFontWeight('bold');
  sh.getRange('A2').setValue('Miesiące: ' + (miesiace.length ? miesiace[0] + ' … ' + miesiace[miesiace.length - 1] : 'brak') +
    '   ·   bieżący miesiąc liczony do dziś   ·   odświeżono ' + Utilities.formatDate(new Date(), CONFIG.STREFA, 'd.MM.yyyy HH:mm')).setFontColor('#6B7A85');

  // 1. suma per osoba
  const nagl = NAGL_SUM.slice(); nagl.splice(10, 0, 'Bilans (zaliczone−norma)');
  sh.getRange(4, 1, 1, nagl.length).setValues([nagl]).setFontWeight('bold').setBackground('#11202B').setFontColor('#FFFFFF');
  const wiersze = osoby.map(function (imie) {
    const rows = wszystkie.filter(function (r) { return String(r[KOL.IMIE]) === imie; });
    const a = agreguj_(rows);
    const etat = CONFIG.ETATY[imie] || 1;
    let norma = 0, nad = 0, nie = 0, nieob = 0, zal = 0;
    const bankOd = CONFIG.BANK_NADGODZIN_OD || '';
    miesiace.forEach(function (m) {
      const rm = rows.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === m; });
      const roz = rozlicz_(imie, rm, m, m === dzisM ? dzis : null, bankPrzed_(imie, m, rows));
      norma += roz.norma; nie += roz.niedogodziny; nieob += roz.nieobecnosciGodz; zal += roz.zaliczone;
      nad = (bankOd && m >= bankOd) ? roz.nadgodziny : nad + roz.nadgodziny;   // bank: saldo narastające, nie suma miesięcy
    });
    const u = urlopRoczny_(imie, dzis.slice(0, 4), rows);
    return [imie, etatTekst_(etat), a.dni, a.zdalnie, dur_(a.godziny), dur_(nieob), dur_(zal), dur_(norma), dur_(nad), dur_(nie),
            dur_(zal - norma), a.urlop, u.tekst + ' · ' + dzis.slice(0, 4), a.l4, a.wolne, a.odbior, a.inne];
  });
  if (wiersze.length) {
    sh.getRange(5, 1, wiersze.length, nagl.length).setValues(wiersze);
    const sum = function (i) { return wiersze.reduce(function (s, w) { return s + (Number(w[i]) || 0); }, 0); };
    sh.getRange(5 + wiersze.length, 1, 1, nagl.length).setValues([[
      'RAZEM', '', sum(2), sum(3), sum(4), sum(5), sum(6), sum(7), sum(8), sum(9), sum(10), sum(11), '', sum(13), sum(14), sum(15), sum(16)
    ]]).setFontWeight('bold').setBorder(true, null, null, null, null, null);
    sh.getRange(5, 5, wiersze.length + 1, 7).setNumberFormat(FORMAT_GODZIN);
    sh.getRange(5, 9, wiersze.length + 1, 1).setFontColor('#0B6E4F');
    sh.getRange(5, 10, wiersze.length + 1, 1).setFontColor('#C2410C');
  }

  // 2. macierz: miesiąc × osoba (godziny), ostatnia kolumna norma miesiąca
  const start = 5 + wiersze.length + 3;
  sh.getRange(start - 1, 1).setValue('Godziny w miesiącach (norma w ostatniej kolumnie)').setFontColor('#6B7A85');
  const naglM = ['Miesiąc'].concat(osoby).concat(['Norma']);
  sh.getRange(start, 1, 1, naglM.length).setValues([naglM]).setFontWeight('bold').setBackground('#11202B').setFontColor('#FFFFFF');
  if (miesiace.length) {
    const mat = miesiace.map(function (m) {
      const rm = wszystkie.filter(function (r) { return String(r[KOL.DATA]).slice(0, 7) === m; });
      return [m].concat(osoby.map(function (imie) {
        return dur_(agreguj_(rm.filter(function (r) { return String(r[KOL.IMIE]) === imie; })).godziny);
      })).concat([dur_(normaM(m))]);
    });
    sh.getRange(start + 1, 1, mat.length, naglM.length).setValues(mat);
    sh.getRange(start + 1, 2, mat.length, naglM.length - 1).setNumberFormat(FORMAT_GODZIN);
  }
  sh.setColumnWidth(1, 120);
  for (let c = 2; c <= Math.max(nagl.length, naglM.length); c++) sh.setColumnWidth(c, 100);
  sh.setHiddenGridlines(true);
  if (ss.getSheets()[0].getName() !== CONFIG.ARKUSZ_RAZEM) { ss.setActiveSheet(sh); ss.moveActiveSheet(1); }
  return sh;
}

function miesiaceZWpisami_() {
  const out = [];
  wszystkieWpisy_().forEach(function (x) {
    const m = String(x.r[KOL.DATA]).slice(0, 7);
    if (/^\d{4}-\d{2}$/.test(m) && out.indexOf(m) === -1) out.push(m);
  });
  return out.sort();
}

function agreguj_(rows) {
  const a = { godziny: 0, dni: 0, zdalnie: 0, urlop: 0, l4: 0, wolne: 0, odbior: 0, inne: 0 };
  (rows || []).forEach(function (r) {
    const typ = String(r[KOL.TYP]);
    const g = Number(r[KOL.GODZINY]) || 0;
    a.godziny += g;
    if (typ === 'Praca' || typ === 'Zdalnie') {
      if (g > 0) a.dni++;
      if (typ === 'Zdalnie' || String(r[KOL.MIEJSCE]) === CONFIG.LOKALIZACJA_ZDALNA) a.zdalnie++;
    }
    if (typ === 'Urlop') a.urlop++;
    if (typ === 'L4' || typ === 'Chorobowe') a.l4++;
    if (typ === 'Wolne') a.wolne++;
    if (typ === 'Odbiór nadgodzin') a.odbior++;
    if (typ === 'Inne') a.inne++;
  });
  return a;
}

/* ------------------------------------------------------------------ */
/* NORMA GODZIN I KALENDARZ                                            */
/* ------------------------------------------------------------------ */

function normaMiesiaca_(mies) {
  if (!CONFIG.NORMA_WG_DNI_ROBOCZYCH) return CONFIG.NORMA_MIESIECZNA;
  return dniRoboczeMiesiaca_(mies).length * 8;
}

function normaDoDzis_(mies, robocze, roboczeDoDzis) {
  if (CONFIG.NORMA_WG_DNI_ROBOCZYCH) return roboczeDoDzis.length * 8;
  return CONFIG.NORMA_MIESIECZNA * roboczeDoDzis.length / Math.max(robocze.length, 1);
}

/** Lista dni roboczych miesiąca (RRRR-MM-DD), bez weekendów i świąt. */
function dniRoboczeMiesiaca_(mies) {
  const rok = Number(mies.slice(0, 4)), nrMies = Number(mies.slice(5, 7));
  const ile = new Date(rok, nrMies, 0).getDate();
  const out = [];
  for (let d = 1; d <= ile; d++) {
    const klucz = mies + '-' + ('0' + d).slice(-2);
    if (dzienRoboczy_(klucz)) out.push(klucz);
  }
  return out;
}

function dzienRoboczy_(dataStr) {
  const cz = dataStr.split('-');
  const dow = new Date(Number(cz[0]), Number(cz[1]) - 1, Number(cz[2])).getDay();
  if (dow === 0 || dow === 6) return false;
  return swietaPL_(Number(cz[0])).indexOf(dataStr) === -1;
}

const SWIETA_CACHE_ = {};

/** Dni ustawowo wolne w Polsce dla danego roku (RRRR-MM-DD). */
function swietaPL_(rok) {
  if (SWIETA_CACHE_[rok]) return SWIETA_CACHE_[rok];
  const stale = ['01-01', '01-06', '05-01', '05-03', '08-15', '11-01', '11-11', '12-24', '12-25', '12-26'];
  const lista = stale.map(function (d) { return rok + '-' + d; });
  const w = wielkanoc_(rok);
  [0, 1, 49, 60].forEach(function (przesun) {      // Wielkanoc, pon. wielkanocny, Zielone Świątki, Boże Ciało
    const d = new Date(w.getFullYear(), w.getMonth(), w.getDate() + przesun);
    lista.push(d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2));
  });
  SWIETA_CACHE_[rok] = lista;
  return lista;
}

/** Niedziela wielkanocna — algorytm Meeusa. */
function wielkanoc_(y) {
  const a = y % 19, b = Math.floor(y / 100), c = y % 100;
  const d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4), kk = c % 4;
  const l = (32 + 2 * e + 2 * i - h - kk) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const mies = Math.floor((h + l - 7 * m + 114) / 31);
  const dzien = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(y, mies - 1, dzien);
}

/* ------------------------------------------------------------------ */
/* RAPORT DZIENNY                                                      */
/* ------------------------------------------------------------------ */

/** Raport dzienny na maila + odświeżenie kart. Trigger ok. 18:30. Można odpalić ręcznie z edytora. */
function raportDzienny(dataStr) {
  const data = (typeof dataStr === 'string' && dataOk_(dataStr)) ? dataStr : dzisStr_();
  const wczoraj = dodajDni_(data, -1);
  const wszystkie = wszystkieWpisy_().map(function (x) { return x.r; });
  const wpisy = wszystkie.filter(function (r) { return String(r[KOL.DATA]) === data; });
  const roboczy = dzienRoboczy_(data);

  const odswiez = function () {
    try { zbudujKarteMiesiaca_(data.slice(0, 7), false); zbudujKarteRazem_(); }
    catch (e) { zglosBlad_('karta ' + data.slice(0, 7), e); }
  };
  if (!roboczy && CONFIG.RAPORT_TYLKO_DNI_ROBOCZE && !wpisy.length) { odswiez(); return; }

  const obecni = wpisy.map(function (r) { return String(r[KOL.IMIE]); });
  const brakujacy = roboczy ? CONFIG.OSOBY.filter(function (o) { return obecni.indexOf(o) === -1; }) : [];
  const wToku = wpisy.filter(function (r) { return String(r[KOL.TYP]) === 'Praca' && r[KOL.START] && !r[KOL.KONIEC]; })
    .map(function (r) { return String(r[KOL.IMIE]) + ' (od ' + r[KOL.START] + ')'; });
  const obecniWczoraj = wszystkie.filter(function (r) { return String(r[KOL.DATA]) === wczoraj; }).map(function (r) { return String(r[KOL.IMIE]); });
  const brakWczoraj = dzienRoboczy_(wczoraj) ? CONFIG.OSOBY.filter(function (o) { return obecniWczoraj.indexOf(o) === -1; }) : [];

  wpisy.sort(function (a, b) { return String(a[KOL.IMIE]) > String(b[KOL.IMIE]) ? 1 : -1; });
  let suma = 0, wiersze = '';
  wpisy.forEach(function (r) {
    const h = Number(r[KOL.GODZINY]) || 0;
    suma += h;
    const prz = przerwy_(r).lista.map(function (x) { return x.od + '–' + (x.do || '…'); }).join(', ') || '—';
    const koniec = (String(r[KOL.TYP]) === 'Praca' && r[KOL.START] && !r[KOL.KONIEC]) ? 'w toku' : (r[KOL.KONIEC] || '—');
    wiersze += '<tr>' + td_(r[KOL.IMIE], 'font-weight:600') + td_(r[KOL.TYP]) + td_(r[KOL.START] || '—') + td_(koniec) +
      td_(prz) + td_(h ? fmtHM_(h) : '—', 'text-align:right;font-variant-numeric:tabular-nums') +
      td_(r[KOL.MIEJSCE] || '') + td_(r[KOL.UWAGI] || '') + '</tr>';
  });

  const html =
    '<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#11202B">' +
    '<h2 style="margin:0 0 4px">Ewidencja czasu — ' + data + ' (' + dzienTygodnia_(data) + (roboczy ? '' : ', dzień wolny') + ')</h2>' +
    '<p style="margin:0 0 16px;color:#6B7A85">Wpisów: ' + wpisy.length + ' / ' + CONFIG.OSOBY.length +
    ' &nbsp;·&nbsp; Suma godzin: <strong>' + fmtHM_(suma) + '</strong></p>' +
    (wpisy.length
      ? '<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:14px">' +
        '<tr style="background:#11202B;color:#fff">' +
        ['Imię', 'Typ', 'Start', 'Koniec', 'Przerwy', 'Godziny', 'Miejsce', 'Uwagi']
          .map(function (h) { return '<th style="padding:8px 10px;text-align:left">' + h + '</th>'; }).join('') +
        '</tr>' + wiersze + '</table>'
      : '<p>Brak wpisów.</p>') +
    (wToku.length ? '<p style="margin-top:12px;color:#6B7A85">Jeszcze w pracy: ' + wToku.join(', ') + '</p>' : '') +
    (brakujacy.length
      ? '<p style="margin-top:16px;padding:10px 12px;background:#FFF4E5;border-left:3px solid #C2410C"><strong>Brak wpisu dziś:</strong> ' + brakujacy.join(', ') + '</p>'
      : (roboczy ? '<p style="margin-top:16px;color:#0B6E4F"><strong>Komplet wpisów.</strong></p>' : '')) +
    (brakWczoraj.length
      ? '<p style="margin-top:8px;padding:10px 12px;background:#FDECE4;border-left:3px solid #C2410C"><strong>Nadal brak wpisu za wczoraj (' + wczoraj + '):</strong> ' + brakWczoraj.join(', ') + '</p>'
      : '') +
    '</div>';

  MailApp.sendEmail({
    to: CONFIG.MAIL_KOORDYNATORA,
    subject: 'Ewidencja czasu — ' + data + ' (' + wpisy.length + '/' + CONFIG.OSOBY.length + ')',
    htmlBody: html
  });
  odswiez();
}

/** Uruchom RAZ z edytora albo z menu: ustawia codzienny raport o 18:30. */
function ustawAutomatyczneRaporty() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'raportDzienny') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('raportDzienny').timeBased().atHour(18).nearMinute(30).everyDays(1).create();
  try { SpreadsheetApp.getUi().alert('Raport dzienny ustawiony na ok. 18:30.'); } catch (e) {}
  return 'Raport dzienny ustawiony na ok. 18:30.';
}

function zglosBlad_(gdzie, e) {
  const tresc = String(e && e.message || e);
  log_('system', 'błąd', '', '', gdzie + ': ' + tresc);
  try { MailApp.sendEmail({ to: CONFIG.MAIL_KOORDYNATORA.split(',')[0].trim(), subject: 'Ewidencja — błąd: ' + gdzie, body: tresc }); } catch (x) {}
}

/* ------------------------------------------------------------------ */
/* ARKUSZE I LOG                                                       */
/* ------------------------------------------------------------------ */

function arkuszWpisow_() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let sh = ss.getSheetByName(CONFIG.ARKUSZ_WPISY);
  if (!sh) sh = ss.insertSheet(CONFIG.ARKUSZ_WPISY);
  const ustawFormaty = function () {
    sh.getRange('A:I').setNumberFormat('@');
    sh.getRange('J:J').setNumberFormat('0.00');
    sh.getRange('K:L').setNumberFormat('@');
  };
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, NAGLOWKI.length).setValues([NAGLOWKI]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.setColumnWidths(1, NAGLOWKI.length, 105);
    ustawFormaty();
  } else {
    const obecne = sh.getRange(1, 1, 1, NAGLOWKI.length).getValues()[0].join('|');
    if (obecne !== NAGLOWKI.join('|')) {
      sh.getRange(1, 1, 1, NAGLOWKI.length).setValues([NAGLOWKI]).setFontWeight('bold');
      ustawFormaty();
    }
  }
  return sh;
}

/**
 * Wszystkie wpisy jako [{wiersz: nrWierszaWArkuszu, r: [kolumny…]}], bez nagłówka.
 * Daty i godziny są normalizowane do tekstu ("2026-10-15", "09:05") także wtedy, gdy Arkusze
 * zamieniły komórkę na datę/godzinę — inaczej wpis z dziś nie byłby rozpoznany.
 */
function wszystkieWpisy_() {
  SpreadsheetApp.flush();
  const sh = arkuszWpisow_();
  const last = sh.getLastRow();
  if (last < 2) return [];
  const dane = sh.getRange(2, 1, last - 1, NAGLOWKI.length).getValues();
  const out = [];
  for (let i = 0; i < dane.length; i++) {
    const r = dane[i];
    r[KOL.DATA] = normDate_(r[KOL.DATA]);
    if (!r[KOL.DATA]) continue;
    [KOL.START, KOL.KONIEC, KOL.PRZ_OD, KOL.PRZ_DO].forEach(function (c) { r[c] = normTime_(r[c]); });
    out.push({ wiersz: i + 2, r: r });
  }
  return out;
}

function jestData_(v) { return Object.prototype.toString.call(v) === '[object Date]' && !isNaN(v.getTime()); }

/** Data z komórki -> "RRRR-MM-DD" (obsługuje tekst, obiekt Date i "15.10.2026"). */
function normDate_(v) {
  if (jestData_(v)) return Utilities.formatDate(v, CONFIG.STREFA, 'yyyy-MM-dd');
  const s = String(v == null ? '' : v).trim();
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s);
  if (m) return m[1] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[3]).slice(-2);
  m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})/.exec(s);
  if (m) return m[3] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2);
  return s;
}

/** Godzina z komórki -> "HH:MM" (tekst, obiekt Date, ułamek doby, lista "09:00, 12:00"). */
function normTime_(v) {
  if (jestData_(v)) return Utilities.formatDate(v, CONFIG.STREFA, 'HH:mm');
  if (typeof v === 'number') { const m = Math.round(v * 1440) % 1440; return ('0' + Math.floor(m / 60)).slice(-2) + ':' + ('0' + (m % 60)).slice(-2); }
  return String(v == null ? '' : v).trim().split(',').map(function (x) { return normalizujCzas_(x) || x.trim(); }).filter(Boolean).join(', ');
}

function wpisDoObiektu_(r) {
  const prz = przerwy_(r);
  const typSur = String(r[KOL.TYP]);
  let faktyczne = 0;
  if (r[KOL.START] && r[KOL.KONIEC] && !prz.otwarta) {
    const dl = roznicaMin_(r[KOL.START], r[KOL.KONIEC]);
    faktyczne = zaokr_(Math.max(0, dl - minutyPrzerw_(r[KOL.START], dl, prz.lista)) / 60);
  }
  return {
    godzinyFaktyczne: faktyczne,
    data: String(r[KOL.DATA]), dzien: dzienTygodnia_(String(r[KOL.DATA])),
    typ: typSur === 'Chorobowe' ? 'L4' : (typSur === 'Zdalnie' ? 'Praca' : typSur),
    start: String(r[KOL.START]), koniec: String(r[KOL.KONIEC]), przerwy: prz.lista, otwartaPrzerwa: prz.otwarta,
    lokalizacja: String(r[KOL.MIEJSCE]), godziny: Number(r[KOL.GODZINY]) || 0, uwagi: String(r[KOL.UWAGI]),
    zapisal: String(r[KOL.ZAPISAL] || ''), zapisano: String(r[KOL.ZAPISANO])
  };
}

function opisWpisu_(r) {
  const typ = String(r[KOL.TYP]);
  if (typ !== 'Praca' && typ !== 'Zdalnie') return typ + (r[KOL.UWAGI] ? ' (' + r[KOL.UWAGI] + ')' : '');
  if (!r[KOL.KONIEC]) return 'w toku od ' + r[KOL.START];
  let s = r[KOL.START] + '–' + r[KOL.KONIEC];
  const prz = przerwy_(r).lista;
  if (prz.length) s += ' bez ' + prz.map(function (x) { return x.od + '–' + x.do; }).join(', ');
  return s + ', ' + fmtHM_(Number(r[KOL.GODZINY]) || 0) + (r[KOL.MIEJSCE] ? ', ' + r[KOL.MIEJSCE] : '');
}

function arkuszLog_() {
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  let sh = ss.getSheetByName(CONFIG.ARKUSZ_LOG);
  if (!sh) {
    sh = ss.insertSheet(CONFIG.ARKUSZ_LOG);
    sh.getRange(1, 1, 1, 6).setValues([['Kiedy', 'Kto', 'Akcja', 'Data wpisu', 'Czyj wpis', 'Szczegóły']]).setFontWeight('bold');
    sh.setFrozenRows(1);
    sh.hideSheet();
  }
  return sh;
}

function log_(kto, akcja, data, imie, szczegoly) {
  try { arkuszLog_().appendRow([terazStr_(), kto, akcja, data, imie, String(szczegoly || '').slice(0, 500)]); } catch (e) {}
}

/* ------------------------------------------------------------------ */
/* NARZĘDZIA                                                           */
/* ------------------------------------------------------------------ */

function dzienTygodnia_(dataStr) {
  const cz = String(dataStr).split('-');
  return DNI_PL[new Date(Number(cz[0]), Number(cz[1]) - 1, Number(cz[2])).getDay()];
}

/** HH:MM -> minuty od północy */
function naMinuty_(hhmm) {
  const cz = String(hhmm).split(':');
  return Number(cz[0]) * 60 + Number(cz[1]);
}

/** różnica w minutach, z obsługą przejścia przez północ */
function roznicaMin_(od, doG) {
  let d = naMinuty_(doG) - naMinuty_(od);
  if (d < 0) d += 24 * 60;
  return d;
}

/** "8:5" / "08:05:00" -> "08:05"; '' gdy nie da się odczytać. */
function normalizujCzas_(v) {
  const m = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(String(v || '').trim());
  if (!m) return '';
  const h = Number(m[1]), mm = Number(m[2]);
  if (h > 23 || mm > 59) return '';
  return ('0' + h).slice(-2) + ':' + ('0' + mm).slice(-2);
}

function dataOk_(v) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(v))) return false;
  const cz = String(v).split('-');
  const dt = new Date(Number(cz[0]), Number(cz[1]) - 1, Number(cz[2]));
  return dt.getMonth() === Number(cz[1]) - 1 && dt.getDate() === Number(cz[2]);
}

function dodajDni_(dataStr, ile) {
  const cz = dataStr.split('-');
  const dt = new Date(Number(cz[0]), Number(cz[1]) - 1, Number(cz[2]) + ile);
  return dt.getFullYear() + '-' + ('0' + (dt.getMonth() + 1)).slice(-2) + '-' + ('0' + dt.getDate()).slice(-2);
}

function dniMiedzy_(od, doD) {
  const out = [];
  let d = od;
  while (d <= doD && out.length < 400) { out.push(d); d = dodajDni_(d, 1); }
  return out;
}

function zaokr_(x) { return Math.round((Number(x) || 0) * 100) / 100; }

/** 7.42 -> "7 h 25 min", 7 -> "7 h", 0.5 -> "30 min" — ten sam format w aplikacji i na karcie PDF. */
function fmtHM_(h) {
  const m = Math.round((Number(h) || 0) * 60), znak = m < 0 ? '−' : '', a = Math.abs(m), g = Math.floor(a / 60), r = a % 60;
  if (!r) return znak + g + ' h';
  if (!g) return znak + r + ' min';
  return znak + g + ' h ' + ('0' + r).slice(-2) + ' min';
}

/** Godziny dziesiętne -> ułamek doby do komórki arkusza z formatem FORMAT_GODZIN (sumuje się jak czas). */
const FORMAT_GODZIN = '[h]" h "mm" min"';
function dur_(h) { return (Number(h) || 0) / 24; }

function fmtGodziny_(h) {
  const m = Math.round(h * 60);
  return Math.floor(m / 60) + ':' + ('0' + (m % 60)).slice(-2) + ' h';
}

function dzisStr_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd'); }
function terazStr_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd HH:mm'); }

function td_(v, styl) {
  return '<td style="padding:7px 10px;border-bottom:1px solid #D6DDE2;' + (styl || '') + '">' + v + '</td>';
}
