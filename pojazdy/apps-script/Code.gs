/* Ewidencja pojazdów RM — backend (Google Apps Script, powiązany z arkuszem).
   Zasady: Regulamin korzystania z pojazdów służbowych oraz rozliczania przejazdów pojazdami prywatnymi.
   Protokół jak w ewidencji czasu: POST text/plain {k: klucz, fn: nazwa, args: [...]} -> {ok, result} | {ok:false, error}.
   Wdrożenie: Wdróż -> Nowe wdrożenie -> Aplikacja internetowa (Wykonaj jako: Ja, Dostęp: Każdy). */

var CONFIG = {
  APP_URL: '',                       // adres aplikacji, np. https://LOGIN.github.io/ewidencja/pojazdy/
  STREFA: 'Europe/Warsaw',
  OKNO_DOPISANIA_DNI: 5,             // ile dni wstecz kierowca może dopisać przejazd (zasada: najpóźniej następnego dnia roboczego)
  PROG_KM_POTWIERDZ: 600,            // przejazd dłuższy niż tyle km wymaga potwierdzenia
  ALERT_DNI: 30,                     // ostrzeżenie o terminach (przegląd, OC, prawo jazdy)
  MIN_CEL_ZNAKOW: 10,
  ZAKAZANE_CELE: ['sprawy fundacji', 'wyjazd służbowy', 'spotkanie', 'sprawy służbowe', 'służbowo', 'sprawy', 'delegacja', 'wyjazd'],
  MIEJSCA: ['G7', 'J48', 'DOM', 'Inne'],                       // jak w ewidencji czasu
  CELE: ['Transport sprzętu', 'Diecezje', 'Marketing', 'Spotkanie', 'Inne'],
  AKCEPTUJACY: ['Mateusz', 'Tomasz', 'Marysia'],     // kto zgadza się na rezerwację i użytek prywatny
  KRAJE: ['PL', 'Zagranica'],
  TYPY_KOSZTOW: ['Paliwo', 'Ładowanie', 'Parking', 'Opłata drogowa', 'Mycie / płyny', 'Serwis / naprawa'],
  TYPY_ZDARZEN: ['Usterka', 'Szkoda / kolizja', 'Wypadek', 'Awaria', 'Mandat']
};

var TAB = {
  Pojazdy:   [['rej','t'],['nazwa','t'],['rodzaj','t'],['paliwo','t'],['licznikStart','n'],['polisaNr','t'],['polisaOd','t'],['polisaDo','t'],['zakres','t'],['przegladDo','t'],['aktywny','t'],['uwagi','t']],
  Kierowcy:  [['imie','t'],['rola','t'],['aktywny','t'],['klucz','t'],['pojazdy','t'],['prawoJazdyDo','t'],['uwagi','t']],
  Przejazdy: [['id','t'],['nr','n'],['data','t'],['kierowca','t'],['rej','t'],['licznikPrzed','n'],['licznikPo','n'],['km','n'],['skad','t'],['dokad','t'],['trasa','t'],['cel','t'],['start','t'],['koniec','t'],['status','t'],['kontrola','t'],['flaga','t'],['uwagi','t'],['zatwierdzil','t'],['zatwierdzonoKiedy','t']],
  Koszty:    [['id','t'],['data','t'],['kierowca','t'],['rej','t'],['typ','t'],['kwota','n'],['ilosc','n'],['licznik','n'],['dokument','t'],['zgoda','t'],['uwagi','t'],['dodano','t']],
  UzytekPrywatny: [['id','t'],['kierowca','t'],['rej','t'],['odData','t'],['doData','t'],['licznikPrzed','n'],['licznikPo','n'],['km','n'],['paliwoPelne','t'],['kraj','t'],['zgoda','t'],['dodano','t']],
  Rezerwacje: [['id','t'],['rej','t'],['kierowca','t'],['odData','t'],['doData','t'],['cel','t'],['akceptowal','t'],['dodano','t']],
  Zdarzenia: [['id','t'],['data','t'],['kierowca','t'],['rej','t'],['typ','t'],['opis','t'],['status','t'],['komentarz','t'],['dodano','t']],
  Zatwierdzenia: [['klucz','t'],['mies','t'],['rej','t'],['kto','t'],['kiedy','t']],
  Dziennik:  [['kiedy','t'],['kto','t'],['rekord','t'],['akcja','t'],['przed','t'],['po','t'],['powod','t']],
  Ustawienia:[['klucz','t'],['wartosc','t'],['opis','t']]
};

/* ============ ARKUSZ ============ */
function ss_() { return SpreadsheetApp.getActiveSpreadsheet(); }
function tab_(nazwa) {
  var s = ss_().getSheetByName(nazwa), def = TAB[nazwa];
  if (!s) {
    s = ss_().insertSheet(nazwa);
    s.getRange(1, 1, 1, def.length).setValues([def.map(function (d) { return d[0]; })]).setFontWeight('bold');
    def.forEach(function (d, i) { if (d[1] === 't') s.getRange(1, i + 1, s.getMaxRows(), 1).setNumberFormat('@'); });
    s.setFrozenRows(1);
  }
  else if (s.getLastColumn() < def.length) {      // zakładka sprzed dodania kolumn: dopisz brakujące nagłówki
    for (var i = s.getLastColumn(); i < def.length; i++) {
      s.getRange(1, i + 1).setValue(def[i][0]).setFontWeight('bold');
      if (def[i][1] === 't') s.getRange(1, i + 1, s.getMaxRows(), 1).setNumberFormat('@');
    }
  }
  return s;
}
function wiersze_(nazwa) {
  var s = tab_(nazwa), def = TAB[nazwa], n = s.getLastRow();
  if (n < 2) return [];
  var v = s.getRange(2, 1, n - 1, def.length).getValues();
  return v.map(function (r, i) {
    var o = { _r: i + 2 };
    def.forEach(function (d, j) { var x = r[j]; o[d[0]] = (d[1] === 'n') ? (x === '' ? '' : Number(x)) : (x === null || x === undefined ? '' : String(x)); });
    return o;
  });
}
function dodaj_(nazwa, o) {
  var s = tab_(nazwa), def = TAB[nazwa];
  var r = s.getLastRow() + 1;
  s.getRange(r, 1, 1, def.length).setValues([def.map(function (d) { return o[d[0]] === undefined ? '' : o[d[0]]; })]);
  o._r = r; return o;
}
function zapisz_(nazwa, o) {
  var def = TAB[nazwa];
  tab_(nazwa).getRange(o._r, 1, 1, def.length).setValues([def.map(function (d) { return o[d[0]] === undefined ? '' : o[d[0]]; })]);
}
function usunWiersz_(nazwa, o) { tab_(nazwa).deleteRow(o._r); }
function ustawienie_(klucz, domyslna) {
  var w = wiersze_('Ustawienia');
  for (var i = 0; i < w.length; i++) if (w[i].klucz === klucz && w[i].wartosc !== '') return w[i].wartosc;
  return domyslna;
}
function dziennik_(kto, rekord, akcja, przed, po, powod) {
  dodaj_('Dziennik', { kiedy: teraz_(), kto: kto, rekord: rekord, akcja: akcja, przed: przed || '', po: po || '', powod: powod || '' });
}

/* ============ CZAS ============ */
function dzis_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd'); }
function hhmm_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'HH:mm'); }
function teraz_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd HH:mm'); }
function dt_(s) { return new Date(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10)), 12); }
function fmt_(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
function dodajDni_(s, n) { var d = dt_(s); d.setDate(d.getDate() + n); return fmt_(d); }
function pl_(s) { return s ? s.slice(8, 10) + '.' + s.slice(5, 7) + '.' + s.slice(0, 4) : ''; }
function dzienTyg_(s) { return dt_(s).getDay(); }
function wielkanoc_(rok) {
  var a = rok % 19, b = Math.floor(rok / 100), c = rok % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25),
      g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4,
      l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451),
      mc = Math.floor((h + l - 7 * m + 114) / 31), dz = ((h + l - 7 * m + 114) % 31) + 1;
  return fmt_(new Date(rok, mc - 1, dz, 12));
}
function swieto_(s) {
  var rok = Number(s.slice(0, 4)), md = s.slice(5);
  if (['01-01', '01-06', '05-01', '05-03', '08-15', '11-01', '11-11', '12-25', '12-26'].indexOf(md) >= 0) return true;
  var w = wielkanoc_(rok);
  return [w, dodajDni_(w, 1), dodajDni_(w, 49), dodajDni_(w, 60)].indexOf(s) >= 0;
}
function roboczy_(s) { var d = dzienTyg_(s); return d !== 0 && d !== 6 && !swieto_(s); }
function poprzedniRoboczy_(s) { var x = dodajDni_(s, -1); while (!roboczy_(x)) x = dodajDni_(x, -1); return x; }
function najwczesniejszaData_() {
  // najpóźniej następnego dnia roboczego: dziś i poprzedni dzień roboczy, ale nie głębiej niż okno
  var t = dzis_(), p = poprzedniRoboczy_(t), gr = dodajDni_(t, -CONFIG.OKNO_DOPISANIA_DNI);
  return p < gr ? p : gr;   // szersze z dwóch
}

/* ============ AUTORYZACJA ============ */
function uzytkownik_(klucz) {
  if (!klucz || String(klucz).length < 40) throw new Error('SESJA: Nieprawidłowy klucz. Poproś administratora o nowy link.');
  var w = wiersze_('Kierowcy');
  for (var i = 0; i < w.length; i++) {
    if (w[i].klucz === klucz) {
      if (w[i].aktywny.toLowerCase() === 'nie') throw new Error('SESJA: To konto jest wyłączone. Skontaktuj się z administratorem.');
      return { imie: w[i].imie, admin: w[i].rola.toLowerCase() === 'admin', pojazdy: w[i].pojazdy, prawoJazdyDo: w[i].prawoJazdyDo, _w: w[i] };
    }
  }
  throw new Error('SESJA: Ten klucz nie jest już ważny. Poproś administratora o nowy link.');
}
function wymagajAdmina_(u) { if (!u.admin) throw new Error('Ta funkcja jest dostępna tylko dla administratora.'); }

/* ============ WALIDACJE ============ */
function liczba_(x, nazwa) {
  var n = Number(String(x).replace(/\s/g, '').replace(',', '.'));
  if (x === '' || x === null || x === undefined || isNaN(n)) throw new Error(nazwa + ': wpisz liczbę.');
  return n;
}
function tekst_(x) { return String(x === null || x === undefined ? '' : x).replace(/\s+/g, ' ').trim(); }
function sprawdzCel_(cel) {
  cel = tekst_(cel);
  if (CONFIG.CELE.indexOf(cel) >= 0 && cel !== 'Inne') return cel;                 // kategoria z listy
  var inne = /^Inne:\s*(.+)$/.exec(cel);
  if (inne) { if (inne[1].length < 3) throw new Error('Opisz cel w polu „Inne”.'); return 'Inne: ' + inne[1]; }
  if (cel.length < CONFIG.MIN_CEL_ZNAKOW) throw new Error('Cel przejazdu opisz konkretnie, np. „odbiór darów od firmy …”, „spotkanie z partnerem projektu …”.');
  var m = cel.toLowerCase().replace(/[.!]+$/, '');
  if (CONFIG.ZAKAZANE_CELE.indexOf(m) >= 0) throw new Error('Opis „' + cel + '” jest zbyt ogólny. Napisz, po co i do kogo jedziesz (np. „transport materiałów do magazynu”).');
  return cel;
}
function dataOk_(s, nazwa) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(s || ''))) throw new Error(nazwa + ': wybierz datę.');
  return s;
}
function wszystkiePojazdy_() {
  var licz = {};
  wiersze_('Przejazdy').forEach(function (p) {
    if (p.status === 'Zakończony' && p.licznikPo !== '') licz[p.rej] = Math.max(licz[p.rej] || 0, p.licznikPo);
  });
  wiersze_('UzytekPrywatny').forEach(function (p) { if (p.licznikPo !== '') licz[p.rej] = Math.max(licz[p.rej] || 0, p.licznikPo); });
  return wiersze_('Pojazdy').filter(function (p) { return p.rej; }).map(function (p) {
    p.licznik = Math.max(licz[p.rej] || 0, p.licznikStart === '' ? 0 : p.licznikStart);
    return p;
  });
}
function pojazdy_() {
  return wszystkiePojazdy_().filter(function (p) { return p.aktywny.toLowerCase() !== 'nie'; });
}
function pojazd_(rej, lista) {
  rej = tekst_(rej).toUpperCase();
  var l = lista || pojazdy_();
  for (var i = 0; i < l.length; i++) if (l[i].rej.toUpperCase() === rej) return l[i];
  throw new Error('Nie ma takiego pojazdu w wykazie.');
}
function mozeJechac_(u, p) {
  if (u.prawoJazdyDo && u.prawoJazdyDo < dzis_()) throw new Error('Twoje prawo jazdy w ewidencji jest po terminie (' + pl_(u.prawoJazdyDo) + '). Skontaktuj się z Koordynatorem Biura.');
  if (!u.admin && u.pojazdy) {
    var dozw = u.pojazdy.split(',').map(function (x) { return tekst_(x).toUpperCase(); }).filter(Boolean);
    if (dozw.length && dozw.indexOf(p.rej.toUpperCase()) < 0) throw new Error('Nie masz uprawnień do pojazdu ' + p.rej + '. Poproś Koordynatora Biura.');
  }
}
function ostrzezeniaPojazdu_(p) {
  var t = dzis_(), lim = dodajDni_(t, CONFIG.ALERT_DNI), a = [];
  [['przegladDo', 'Przegląd'], ['polisaDo', 'Polisa']].forEach(function (x) {
    var d = p[x[0]];
    if (!d) return;
    if (d < t) a.push({ poziom: 'blad', tekst: x[1] + ' po terminie (' + pl_(d) + ')' });
    else if (d <= lim) a.push({ poziom: 'info', tekst: x[1] + ' do ' + pl_(d) });
  });
  return a;
}
function oknoDopisania_(u, data) {
  if (u.admin) return;
  if (data > dzis_()) throw new Error('Data z przyszłości.');
  if (data < najwczesniejszaData_()) throw new Error('Przejazd dopisujesz najpóźniej następnego dnia roboczego. Starsze wpisy dodaje administrator.');
}
function zatwierdzony_(mies, rej) {
  var k = mies + '|' + rej, w = wiersze_('Zatwierdzenia');
  for (var i = 0; i < w.length; i++) if (w[i].klucz === k) return w[i];
  return null;
}
function zablokowany_(data, rej) {
  var z = zatwierdzony_(data.slice(0, 7), rej);
  if (z) throw new Error('Miesiąc dla pojazdu ' + rej + ' jest już zatwierdzony. Poproś administratora o cofnięcie zatwierdzenia.');
}
function nakladanie_(rej, przed, po, pomin) {
  wiersze_('UzytekPrywatny').forEach(function (u) {
    if (u.rej === rej && u.id !== pomin && przed < u.licznikPo && po > u.licznikPrzed) throw new Error('Ten zakres licznika (' + przed + '–' + po + ') jest już zajęty przez użytek prywatny (' + u.kierowca + ', ' + pl_(u.odData) + ').');
  });
  var w = wiersze_('Przejazdy');
  for (var i = 0; i < w.length; i++) {
    var p = w[i];
    if (p.rej !== rej || p.status !== 'Zakończony' || p.id === pomin) continue;
    if (przed < p.licznikPo && po > p.licznikPrzed) throw new Error('Ten zakres licznika (' + przed + '–' + po + ') jest już zajęty przez przejazd z ' + p.data + ' (' + p.licznikPrzed + '–' + p.licznikPo + ', ' + p.kierowca + ').');
  }
}
function nowyId_() { return Utilities.getUuid().slice(0, 8); }
function nrKolejny_(rej, rok) {
  var n = 0; wiersze_('Przejazdy').forEach(function (p) { if (p.rej === rej && p.data.slice(0, 4) === rok) n++; });
  return n + 1;
}
function ostatniePrzejazdy_() {
  var m = {};
  wiersze_('Przejazdy').forEach(function (p) {
    if (p.status !== 'Zakończony') return;
    var k = p.data + ' ' + p.koniec, x = m[p.rej];      // ostatni = najwyższy licznik (nie cofa się), przy remisie późniejszy wpis
    if (!x || p.licznikPo > x.licznik || (p.licznikPo === x.licznik && k > x.k)) m[p.rej] = { k: k, data: p.data, koniec: p.koniec, kierowca: p.kierowca, dokad: p.dokad, licznik: p.licznikPo };
  });
  wiersze_('UzytekPrywatny').forEach(function (u) {      // po użytku prywatnym miejsce nie jest znane
    var x = m[u.rej];
    if (!x || u.licznikPo > x.licznik) m[u.rej] = { k: u.doData, data: u.doData, koniec: '', kierowca: u.kierowca, dokad: '', licznik: u.licznikPo, prywatnie: true };
  });
  return m;
}
function opisPrzejazdu_(p) { return p.data + ' ' + p.rej + ' ' + p.licznikPrzed + '→' + (p.licznikPo === '' ? '…' : p.licznikPo) + ' ' + p.skad + '→' + p.dokad + ' (' + p.cel + ')'; }

/* ============ API: KIEROWCA ============ */
var API = {};

API.konfig = function (u) {
  var lista = pojazdy_().filter(function (p) {
    if (u.admin || !u.pojazdy) return true;
    var d = u.pojazdy.split(',').map(function (x) { return tekst_(x).toUpperCase(); }).filter(Boolean);
    return !d.length || d.indexOf(p.rej.toUpperCase()) >= 0;
  });
  var otwarte = {}, ost = ostatniePrzejazdy_(), rez = wiersze_('Rezerwacje'), dzis = dzis_();
  wiersze_('Przejazdy').forEach(function (p) { if (p.status === 'W trakcie') otwarte[p.rej] = { kto: p.kierowca, od: p.start, data: p.data }; });
  var wynik = {
    imie: u.imie, admin: u.admin, dzisiaj: dzis_(), najwczesniejszaData: najwczesniejszaData_(),
    pojazdy: lista.map(function (p) {
      return { rej: p.rej, nazwa: p.nazwa, rodzaj: p.rodzaj, paliwo: p.paliwo, licznik: p.licznik, przegladDo: p.przegladDo, polisaDo: p.polisaDo,
               ostrzezenia: ostrzezeniaPojazdu_(p), wTrasie: otwarte[p.rej] || null, rezerwacja: rezerwacjaNa_(p.rej, dzis, rez),
               ostatni: ost[p.rej] ? { data: ost[p.rej].data, koniec: ost[p.rej].koniec, kierowca: ost[p.rej].kierowca, dokad: ost[p.rej].dokad, prywatnie: !!ost[p.rej].prywatnie } : null };
    }),
    miejsca: CONFIG.MIEJSCA, cele: CONFIG.CELE,
    typyKosztow: CONFIG.TYPY_KOSZTOW, typyZdarzen: CONFIG.TYPY_ZDARZEN,
    akceptujacy: CONFIG.AKCEPTUJACY, kraje: CONFIG.KRAJE,
    prawoJazdyDo: u.prawoJazdyDo || '', progKm: CONFIG.PROG_KM_POTWIERDZ
  };
  if (u.admin) {
    wynik.osoby = wiersze_('Kierowcy').filter(function (k) { return k.aktywny.toLowerCase() !== 'nie'; }).map(function (k) { return k.imie; });
    wynik.arkusz = ss_().getUrl();
  }
  return wynik;
};

API.stanJazdy = function (u) {
  var w = wiersze_('Przejazdy').filter(function (p) { return p.kierowca === u.imie; });
  var otwarta = null, dzis = [], ostatni = null, t = dzis_();
  w.forEach(function (p) {
    if (p.status === 'W trakcie') otwarta = p;
    if (p.data === t) dzis.push(p);
    if (p.status === 'Zakończony' && (!ostatni || (p.data + p.koniec) > (ostatni.data + ostatni.koniec))) ostatni = p;
  });
  dzis.sort(function (a, b) { return a.start < b.start ? -1 : 1; });
  var od = najwczesniejszaData_();
  var ostatnie = w.filter(function (p) { return p.status === 'Zakończony' && p.data >= od; })
    .sort(function (a, b) { return (a.data + a.start) < (b.data + b.start) ? 1 : -1; }).slice(0, 15);
  return { dzis: t, otwarta: otwarta, dzisiejsze: dzis, ostatnie: ostatnie, ostatni: ostatni ? { rej: ostatni.rej, dokad: ostatni.dokad } : null };
};

API.startJazdy = function (u, d) {
  var lista = pojazdy_(), p = pojazd_(d.rej, lista);
  mozeJechac_(u, p);
  var wszystkie = wiersze_('Przejazdy');
  wszystkie.forEach(function (x) {
    if (x.status !== 'W trakcie') return;
    if (x.kierowca === u.imie) throw new Error('Masz już rozpoczętą jazdę (' + x.rej + ' od ' + x.start + '). Najpierw ją zakończ.');
    if (x.rej === p.rej) throw new Error('Pojazd ' + p.rej + ' jest w trasie: ' + x.kierowca + ' od ' + x.start + '. Poczekaj na zakończenie jazdy.');
  });
  var rz = rezerwacjaNa_(p.rej, dzis_());
  if (rz && rz.kto !== u.imie && !u.admin) throw new Error('Pojazd jest zarezerwowany: ' + rz.kto + ' (' + pl_(rz.od) + '–' + pl_(rz.do) + ').');
  if (d.kontrola !== true) throw new Error('Potwierdź kontrolę pojazdu przed jazdą (licznik, paliwo, uszkodzenia, opony, dokumenty).');
  var przed = Math.round(liczba_(d.licznik, 'Licznik przed jazdą'));
  if (przed < 0) throw new Error('Licznik przed jazdą: liczba nie może być ujemna.');
  var flaga = '';
  if (przed < p.licznik) throw new Error('Licznik (' + przed + ') jest mniejszy niż ostatni zapis tego pojazdu (' + p.licznik + ' km). Sprawdź odczyt.');
  if (przed > p.licznik) flaga = 'Luka licznika: +' + (przed - p.licznik) + ' km od ostatniego zapisu';
  var skad = tekst_(d.skad), ost = ostatniePrzejazdy_()[p.rej];
  if (!skad && ost) skad = ost.dokad;
  if (!skad) throw new Error('Wpisz, skąd wyruszasz (to pierwszy zapis tego pojazdu).');
  var cel = tekst_(d.cel) ? sprawdzCel_(d.cel) : '';      // cel można podać przy zdaniu pojazdu
  var t = dzis_(), id = nowyId_();
  var o = dodaj_('Przejazdy', { id: id, nr: nrKolejny_(p.rej, t.slice(0, 4)), data: t, kierowca: u.imie, rej: p.rej, licznikPrzed: przed, licznikPo: '', km: '',
    skad: skad, dokad: '', trasa: tekst_(d.trasa), cel: cel, start: hhmm_(), koniec: '', status: 'W trakcie', kontrola: 'tak', flaga: flaga, uwagi: tekst_(d.uwagi) });
  return { przejazd: o, ostrzezenia: ostrzezeniaPojazdu_(p) };
};

API.koniecJazdy = function (u, d) {
  var o = null;
  wiersze_('Przejazdy').forEach(function (p) { if (p.kierowca === u.imie && p.status === 'W trakcie') o = p; });
  if (!o) throw new Error('Nie masz rozpoczętej jazdy.');
  var cel = sprawdzCel_(tekst_(d.cel) || o.cel);
  var po = Math.round(liczba_(d.licznik, 'Licznik po jeździe'));
  if (po < o.licznikPrzed) throw new Error('Licznik po jeździe (' + po + ') nie może być mniejszy niż przed (' + o.licznikPrzed + ').');
  var km = po - o.licznikPrzed;
  if (km > CONFIG.PROG_KM_POTWIERDZ && !d.potwierdz) throw new Error('POTWIERDZ: To ' + km + ' km. Czy odczyt licznika jest poprawny?');
  var dokad = tekst_(d.dokad); if (!dokad) throw new Error('Wpisz, gdzie zostawiasz pojazd.');
  nakladanie_(o.rej, o.licznikPrzed, po, o.id);
  o.licznikPo = po; o.km = km; o.dokad = dokad; o.koniec = hhmm_(); o.status = 'Zakończony';
  if (d.trasa !== undefined && tekst_(d.trasa)) o.trasa = tekst_(d.trasa);
  o.cel = cel;
  if (tekst_(d.uwagi)) o.uwagi = (o.uwagi ? o.uwagi + ' | ' : '') + tekst_(d.uwagi);
  zapisz_('Przejazdy', o);
  return { przejazd: o };
};

API.dopiszPrzejazd = function (u, d) {
  var o = dopiszPrzejazd_(u, u.imie, d);
  return { przejazd: o };
};
function dopiszPrzejazd_(u, kierowca, d) {
  var data = dataOk_(d.data, 'Data'), p = pojazd_(d.rej);
  oknoDopisania_(u, data);
  zablokowany_(data, p.rej);
  mozeJechac_(u.admin ? { admin: true, pojazdy: '' } : u, p);
  var przed = Math.round(liczba_(d.licznikPrzed, 'Licznik przed')), po = Math.round(liczba_(d.licznikPo, 'Licznik po'));
  if (po <= przed) throw new Error('Licznik po musi być większy niż przed.');
  nakladanie_(p.rej, przed, po, '');
  var skad = tekst_(d.skad), dokad = tekst_(d.dokad);
  if (!skad || !dokad) throw new Error('Wpisz miejsce rozpoczęcia i zakończenia.');
  var cel = sprawdzCel_(d.cel), km = po - przed;
  var o = dodaj_('Przejazdy', { id: nowyId_(), nr: nrKolejny_(p.rej, data.slice(0, 4)), data: data, kierowca: kierowca, rej: p.rej, licznikPrzed: przed, licznikPo: po, km: km,
    skad: skad, dokad: dokad, trasa: tekst_(d.trasa), cel: cel, start: tekst_(d.start), koniec: tekst_(d.koniec), status: 'Zakończony', kontrola: '', flaga: 'Wpis ręczny', uwagi: tekst_(d.uwagi) });
  dziennik_(u.imie, o.id, 'dopisanie' + (u.imie !== kierowca ? ' za ' + kierowca : ''), '', opisPrzejazdu_(o), '');
  return o;
}

API.poprawPrzejazd = function (u, id, d, powod) {
  var o = null; wiersze_('Przejazdy').forEach(function (p) { if (p.id === id) o = p; });
  if (!o) throw new Error('Nie znaleziono wpisu.');
  if (o.kierowca !== u.imie && !u.admin) throw new Error('Możesz poprawić tylko własny wpis.');
  if (o.status !== 'Zakończony') throw new Error('Rozpoczętą jazdę zakończ przyciskiem Zdaj pojazd.');
  powod = tekst_(powod);
  if (powod.length < 3) throw new Error('Wpisz powód poprawki (np. „pomyłka w odczycie licznika”).');
  oknoDopisania_(u, o.data); zablokowany_(o.data, o.rej);
  var data = dataOk_(d.data, 'Data'), p = pojazd_(d.rej);
  oknoDopisania_(u, data); zablokowany_(data, p.rej);
  var przed = Math.round(liczba_(d.licznikPrzed, 'Licznik przed')), po = Math.round(liczba_(d.licznikPo, 'Licznik po'));
  if (po <= przed) throw new Error('Licznik po musi być większy niż przed.');
  nakladanie_(p.rej, przed, po, o.id);
  var skad = tekst_(d.skad), dokad = tekst_(d.dokad);
  if (!skad || !dokad) throw new Error('Wpisz miejsce rozpoczęcia i zakończenia.');
  var cel = sprawdzCel_(d.cel), opisPrzed = opisPrzejazdu_(o);
  o.data = data; o.rej = p.rej; o.licznikPrzed = przed; o.licznikPo = po; o.km = po - przed;
  o.skad = skad; o.dokad = dokad; o.cel = cel; o.trasa = tekst_(d.trasa);
  o.flaga = (o.flaga && o.flaga.indexOf('Poprawione') < 0 ? o.flaga + ' | ' : '') + (o.flaga && o.flaga.indexOf('Poprawione') >= 0 ? o.flaga : 'Poprawione');
  zapisz_('Przejazdy', o);
  dziennik_(u.imie, o.id, 'poprawka', opisPrzed, opisPrzejazdu_(o), powod);
  return { przejazd: o };
};

API.usunJazde = function (u, id, powod) {
  var o = null; wiersze_('Przejazdy').forEach(function (p) { if (p.id === id) o = p; });
  if (!o) throw new Error('Nie znaleziono wpisu.');
  if (o.kierowca !== u.imie && !u.admin) throw new Error('Możesz usunąć tylko własny wpis.');
  if (!u.admin && o.status === 'Zakończony') oknoDopisania_(u, o.data);
  zablokowany_(o.data, o.rej);
  dziennik_(u.imie, o.id, 'usunięcie', opisPrzejazdu_(o), '', tekst_(powod) || 'usunięte w aplikacji');
  usunWiersz_('Przejazdy', o);
  return true;
};

function kosztyWspolne_(u, d) {
  var p = pojazd_(d.rej), data = dataOk_(d.data || dzis_(), 'Data');
  if (!u.admin && data > dzis_()) throw new Error('Data z przyszłości.');
  zablokowany_(data, p.rej);
  return { p: p, data: data };
}
function kosztPozycja_(x) {
  var typ = tekst_(x.typ);
  if (CONFIG.TYPY_KOSZTOW.indexOf(typ) < 0) throw new Error('Wybierz rodzaj kosztu.');
  var kwota = liczba_(x.kwota, typ);
  if (kwota <= 0) throw new Error(typ + ': kwota musi być większa od zera.');
  return { typ: typ, kwota: Math.round(kwota * 100) / 100 };
}
API.dodajKoszt = function (u, d) {
  var w = kosztyWspolne_(u, d), x = kosztPozycja_(d);
  var ilosc = (d.ilosc === '' || d.ilosc === undefined || d.ilosc === null) ? '' : liczba_(d.ilosc, 'Ilość');
  var licznik = (d.licznik === '' || d.licznik === undefined || d.licznik === null) ? '' : Math.round(liczba_(d.licznik, 'Licznik'));
  var o = dodaj_('Koszty', { id: nowyId_(), data: w.data, kierowca: u.imie, rej: w.p.rej, typ: x.typ, kwota: x.kwota, ilosc: ilosc, licznik: licznik,
    dokument: tekst_(d.dokument), zgoda: tekst_(d.zgoda), uwagi: tekst_(d.uwagi), dodano: teraz_() });
  return { koszt: o };
};
// kilka pozycji naraz (paliwo, parking, drogowe, płyny): wszystkie albo żadna
API.dodajKoszty = function (u, d) {
  var w = kosztyWspolne_(u, d), poz = d.pozycje || [];
  if (!poz.length) throw new Error('Wpisz kwotę.');
  var gotowe = poz.map(kosztPozycja_);
  var zapisane = gotowe.map(function (x) {
    return dodaj_('Koszty', { id: nowyId_(), data: w.data, kierowca: u.imie, rej: w.p.rej, typ: x.typ, kwota: x.kwota, ilosc: '', licznik: '', dokument: '', zgoda: '', uwagi: '', dodano: teraz_() });
  });
  return { koszty: zapisane };
};
API.usunKoszt = function (u, id) {
  var o = null; wiersze_('Koszty').forEach(function (p) { if (p.id === id) o = p; });
  if (!o) throw new Error('Nie znaleziono wpisu.');
  if (o.kierowca !== u.imie && !u.admin) throw new Error('Możesz usunąć tylko własny wpis.');
  zablokowany_(o.data, o.rej);
  dziennik_(u.imie, o.id, 'usunięcie kosztu', o.data + ' ' + o.rej + ' ' + o.typ + ' ' + o.kwota, '', 'usunięte w aplikacji');
  usunWiersz_('Koszty', o);
  return true;
};

API.zglosZdarzenie = function (u, d) {
  var typ = tekst_(d.typ);
  if (CONFIG.TYPY_ZDARZEN.indexOf(typ) < 0) throw new Error('Wybierz rodzaj zgłoszenia.');
  var p = pojazd_(d.rej);
  var opis = tekst_(d.opis); if (opis.length < 10) throw new Error('Opisz zdarzenie (co, gdzie, kiedy) w kilku słowach.');
  var o = dodaj_('Zdarzenia', { id: nowyId_(), data: dzis_(), kierowca: u.imie, rej: p.rej, typ: typ, opis: opis, status: 'Nowe', dodano: teraz_() });
  return { zdarzenie: o };
};

/* ============ API: ADMIN ============ */
API.flota = function (u, mies) {
  wymagajAdmina_(u); okres_(mies);
  var lista = pojazdy_(), tr = wiersze_('Przejazdy'), ko = wiersze_('Koszty'), t = dzis_();
  var zatw = {}; if (mies.length === 7) wiersze_('Zatwierdzenia').forEach(function (z) { if (z.mies === mies) zatw[z.rej] = z; });
  var poj = lista.map(function (p) {
    var x = { rej: p.rej, nazwa: p.nazwa, licznik: p.licznik, km: 0, przejazdy: 0, otwarte: 0, luki: 0, wTrasie: null, litry: 0, paliwoKwota: 0, koszty: 0, ostrzezenia: ostrzezeniaPojazdu_(p),
              zatwierdzone: zatw[p.rej] ? { kto: zatw[p.rej].kto, kiedy: zatw[p.rej].kiedy } : null };
    tr.forEach(function (r) {
      if (r.rej !== p.rej || r.data.indexOf(mies) !== 0) return;
      if (r.status === 'W trakcie') { x.otwarte++; if (r.data === t) x.wTrasie = { kto: r.kierowca, od: r.start }; return; }
      x.km += r.km; x.przejazdy++;
      if (r.flaga && r.flaga.indexOf('Luka') === 0) x.luki++;
    });
    ko.forEach(function (k) {
      if (k.rej !== p.rej || k.data.indexOf(mies) !== 0) return;
      x.koszty += k.kwota;
      if (k.typ === 'Paliwo' && k.ilosc !== '') { x.litry += k.ilosc; x.paliwoKwota += k.kwota; }
    });
    x.koszty = Math.round(x.koszty * 100) / 100;
    x.zuzycie = (x.litry && x.km) ? Math.round(x.litry / x.km * 1000) / 10 : null;     // l/100 km (orientacyjnie)
    return x;
  });
  var kier = wiersze_('Kierowcy').filter(function (k) { return k.aktywny.toLowerCase() !== 'nie'; });
  var lim = dodajDni_(t, CONFIG.ALERT_DNI), prawa = [];
  kier.forEach(function (k) { if (k.prawoJazdyDo && k.prawoJazdyDo <= lim) prawa.push({ imie: k.imie, do: k.prawoJazdyDo, po: k.prawoJazdyDo < t }); });
  var zd = wiersze_('Zdarzenia').filter(function (z) { return z.status !== 'Zamknięte'; }).sort(function (a, b) { return a.dodano < b.dodano ? 1 : -1; });
  var sumy = { km: 0, przejazdy: 0, koszty: 0 }, wgK = {};
  tr.forEach(function (r) {
    if (r.data.indexOf(mies) !== 0 || r.status !== 'Zakończony') return;
    sumy.km += r.km; sumy.przejazdy++;
    var k = wgK[r.kierowca] = wgK[r.kierowca] || { imie: r.kierowca, km: 0, przejazdy: 0 }; k.km += r.km; k.przejazdy++;
  });
  ko.forEach(function (k) { if (k.data.indexOf(mies) === 0) sumy.koszty += k.kwota; });
  sumy.koszty = Math.round(sumy.koszty * 100) / 100; sumy.aktywne = lista.length;
  sumy.kierowcy = Object.keys(wgK).map(function (n) { return wgK[n]; }).sort(function (a, b) { return b.km - a.km; });
  return { mies: mies, sumy: sumy, pojazdy: poj, prawaJazdy: prawa, zdarzenia: zd, osoby: kier.map(function (k) { return k.imie; }) };
};

API.przejazdyPojazdu = function (u, mies, rej) {
  wymagajAdmina_(u); okres_(mies);
  var tr = wiersze_('Przejazdy').filter(function (p) { return p.rej === rej && p.data.indexOf(mies) === 0; })
    .sort(function (a, b) { return (a.data + a.start) < (b.data + b.start) ? -1 : 1; });
  // kontrola ciągłości licznika (§8.6a): poprzedni „po” = następny „przed”
  var prev = null;
  tr.forEach(function (p) {
    p.lukaKm = (prev !== null && p.status === 'Zakończony' && p.licznikPrzed !== prev) ? p.licznikPrzed - prev : 0;
    if (p.status === 'Zakończony') prev = p.licznikPo;
  });
  return tr;
};

API.zatwierdzMiesiac = function (u, mies, rej, cofnij) {
  wymagajAdmina_(u);
  var klucz = mies + '|' + rej, z = zatwierdzony_(mies, rej);
  if (cofnij) {
    if (!z) throw new Error('Ten miesiąc nie jest zatwierdzony.');
    usunWiersz_('Zatwierdzenia', z);
    dziennik_(u.imie, klucz, 'cofnięcie zatwierdzenia', '', '', '');
    return true;
  }
  if (z) throw new Error('Już zatwierdzone (' + z.kto + ').');
  var otwarte = wiersze_('Przejazdy').filter(function (p) { return p.rej === rej && p.data.slice(0, 7) === mies && p.status === 'W trakcie'; });
  if (otwarte.length) throw new Error('Są niezakończone jazdy (' + otwarte.map(function (p) { return p.kierowca + ' ' + p.data; }).join(', ') + '). Zamknij je przed zatwierdzeniem.');
  dodaj_('Zatwierdzenia', { klucz: klucz, mies: mies, rej: rej, kto: u.imie, kiedy: teraz_() });
  wiersze_('Przejazdy').forEach(function (p) {
    if (p.rej === rej && p.data.slice(0, 7) === mies) { p.zatwierdzil = u.imie; p.zatwierdzonoKiedy = teraz_(); zapisz_('Przejazdy', p); }
  });
  dziennik_(u.imie, klucz, 'zatwierdzenie miesiąca', '', '', '');
  return true;
};

API.zmienZdarzenie = function (u, id, status, komentarz) {
  wymagajAdmina_(u);
  if (['Nowe', 'W toku', 'Zamknięte'].indexOf(status) < 0) throw new Error('Zły status.');
  var o = null; wiersze_('Zdarzenia').forEach(function (p) { if (p.id === id) o = p; });
  if (!o) throw new Error('Nie znaleziono zgłoszenia.');
  o.status = status; if (tekst_(komentarz)) o.komentarz = tekst_(komentarz);
  zapisz_('Zdarzenia', o);
  return true;
};

API.wpisAdmin = function (u, d) {
  wymagajAdmina_(u);
  var kier = tekst_(d.kierowca); if (!kier) throw new Error('Wybierz kierowcę.');
  return { przejazd: dopiszPrzejazd_(u, kier, d) };
};




/* ============ API: REZERWACJE ============ */
function rezerwacjaNa_(rej, data, lista) {
  var l = lista || wiersze_('Rezerwacje'), r = null;
  l.forEach(function (x) { if (x.rej === rej && x.odData <= data && data <= x.doData) r = { kto: x.kierowca, od: x.odData, do: x.doData, cel: x.cel, id: x.id }; });
  return r;
}
API.rezerwuj = function (u, d) {
  var p = pojazd_(d.rej), od = dataOk_(d.od, 'Data zabrania'), do_ = dataOk_(d.do, 'Data zdania'), t = dzis_();
  if (od > do_) throw new Error('Data zdania jest przed datą zabrania.');
  if (od < t && !u.admin) throw new Error('Rezerwacja nie może zaczynać się w przeszłości.');
  var cel = sprawdzCel_(d.cel), kto = tekst_(d.akceptowal);
  if (CONFIG.AKCEPTUJACY.indexOf(kto) < 0) throw new Error('Wskaż, kto zaakceptował rezerwację.');
  wiersze_('Rezerwacje').forEach(function (r) {
    if (r.rej === p.rej && od <= r.doData && do_ >= r.odData) throw new Error('Pojazd jest już zarezerwowany: ' + r.kierowca + ' (' + pl_(r.odData) + '–' + pl_(r.doData) + ').');
  });
  var o = dodaj_('Rezerwacje', { id: nowyId_(), rej: p.rej, kierowca: u.imie, odData: od, doData: do_, cel: cel, akceptowal: kto, dodano: teraz_() });
  return { rezerwacja: o };
};
API.rezerwacje = function (u) {
  var t = dzis_();
  return wiersze_('Rezerwacje').filter(function (r) { return r.doData >= t; }).sort(function (a, b) { return a.odData < b.odData ? -1 : 1; });
};
API.usunRezerwacje = function (u, id) {
  var o = null; wiersze_('Rezerwacje').forEach(function (r) { if (r.id === id) o = r; });
  if (!o) throw new Error('Nie znaleziono rezerwacji.');
  if (o.kierowca !== u.imie && !u.admin) throw new Error('Możesz usunąć tylko własną rezerwację.');
  dziennik_(u.imie, o.id, 'usunięcie rezerwacji', o.rej + ' ' + o.odData + '–' + o.doData + ' ' + o.kierowca, '', '');
  usunWiersz_('Rezerwacje', o);
  return true;
};

/* ============ API: UŻYTEK PRYWATNY (auto służbowe zabrane prywatnie) ============ */
API.uzytekPrywatny = function (u, d) {
  var p = pojazd_(d.rej), od = dataOk_(d.od, 'Data zabrania'), do_ = dataOk_(d.do, 'Data zdania');
  if (od > do_) throw new Error('Data zdania jest przed datą zabrania.');
  if (do_ > dzis_()) throw new Error('Data zdania z przyszłości. Zapisz użytek po zdaniu auta.');
  var przed = Math.round(liczba_(d.licznikPrzed, 'Licznik przed')), po = Math.round(liczba_(d.licznikPo, 'Licznik po'));
  if (po <= przed) throw new Error('Licznik po musi być większy niż przed.');
  nakladanie_(p.rej, przed, po, '');
  var paliwo = tekst_(d.paliwo).toLowerCase();
  if (paliwo !== 'tak' && paliwo !== 'nie') throw new Error('Zaznacz, czy paliwo zostało uzupełnione do pełna.');
  var kraj = tekst_(d.kraj); if (CONFIG.KRAJE.indexOf(kraj) < 0) throw new Error('Wybierz: PL czy zagranica.');
  var kto = tekst_(d.zgoda); if (CONFIG.AKCEPTUJACY.indexOf(kto) < 0) throw new Error('Wskaż, kto wyraził zgodę na zabranie auta.');
  var o = dodaj_('UzytekPrywatny', { id: nowyId_(), kierowca: u.imie, rej: p.rej, odData: od, doData: do_, licznikPrzed: przed, licznikPo: po, km: po - przed,
    paliwoPelne: paliwo, kraj: kraj, zgoda: kto, dodano: teraz_() });
  dziennik_(u.imie, o.id, 'użytek prywatny', '', p.rej + ' ' + od + '–' + do_ + ' ' + przed + '→' + po + ' (zgoda: ' + kto + ')', '');
  return { uzytek: o };
};
API.uzytkiMoje = function (u) {
  return wiersze_('UzytekPrywatny').filter(function (x) { return x.kierowca === u.imie; }).sort(function (a, b) { return a.odData < b.odData ? 1 : -1; }).slice(0, 8);
};
API.usunUzytek = function (u, id) {
  var o = null; wiersze_('UzytekPrywatny').forEach(function (x) { if (x.id === id) o = x; });
  if (!o) throw new Error('Nie znaleziono wpisu.');
  if (o.kierowca !== u.imie && !u.admin) throw new Error('Możesz usunąć tylko własny wpis.');
  dziennik_(u.imie, o.id, 'usunięcie użytku prywatnego', o.rej + ' ' + o.odData + '–' + o.doData + ' ' + o.licznikPrzed + '→' + o.licznikPo, '', '');
  usunWiersz_('UzytekPrywatny', o);
  return true;
};

/* ============ API: GDZIE SĄ AUTA TERAZ ============ */
API.gdzieAuta = function (u) {
  var t = dzis_(), tr = wiersze_('Przejazdy'), rez = wiersze_('Rezerwacje'), ost = ostatniePrzejazdy_();
  return pojazdy_().map(function (p) {
    var x = { rej: p.rej, nazwa: p.nazwa, licznik: p.licznik, ostrzezenia: ostrzezeniaPojazdu_(p), wTrasie: null, rezerwacja: rezerwacjaNa_(p.rej, t, rez), nastepna: null,
              ostatni: ost[p.rej] ? { data: ost[p.rej].data, koniec: ost[p.rej].koniec, kierowca: ost[p.rej].kierowca, dokad: ost[p.rej].dokad, prywatnie: !!ost[p.rej].prywatnie } : null };
    tr.forEach(function (r) { if (r.rej === p.rej && r.status === 'W trakcie') x.wTrasie = { kto: r.kierowca, od: r.start, data: r.data, skad: r.skad, cel: r.cel }; });
    rez.forEach(function (r) { if (r.rej === p.rej && r.odData > t && (!x.nastepna || r.odData < x.nastepna.od)) x.nastepna = { kto: r.kierowca, od: r.odData, do: r.doData, cel: r.cel }; });
    return x;
  });
};

/* ============ API: WIDOKI ADMINA — per pojazd i per pracownik ============ */
function okres_(o) { if (!/^\d{4}(-\d{2})?$/.test(String(o || ''))) throw new Error('Zły okres.'); return o; }
function sumujPrzejazdy_(tr, kluczGrupy, nazwaGrupy) {
  var g = {}, km = 0, liczba = 0;
  tr.forEach(function (p) {
    if (p.status !== 'Zakończony') return;
    km += p.km; liczba++;
    var k = p[kluczGrupy], x = g[k] = g[k] || { klucz: k, km: 0, przejazdy: 0, ostatnio: '' };
    x.km += p.km; x.przejazdy++; if (p.data > x.ostatnio) x.ostatnio = p.data;
  });
  var lista = Object.keys(g).map(function (k) { return g[k]; }).sort(function (a, b) { return b.km - a.km; });
  return { km: km, liczba: liczba, grupy: lista };
}
function przejazdyOkresu_(okres, warunek) {
  return wiersze_('Przejazdy').filter(function (p) { return p.data.indexOf(okres) === 0 && warunek(p); })
    .sort(function (a, b) { return (a.data + a.start) < (b.data + b.start) ? 1 : -1; });   // najnowsze na górze
}
API.dziennikPojazdu = function (u, rej, okres) {
  wymagajAdmina_(u); okres_(okres);
  var tr = przejazdyOkresu_(okres, function (p) { return p.rej === rej; });
  var s = sumujPrzejazdy_(tr, 'kierowca');
  var up = wiersze_('UzytekPrywatny').filter(function (x) { return x.rej === rej && x.odData.indexOf(okres) === 0; }).sort(function (a, b) { return a.odData < b.odData ? 1 : -1; });
  return { rej: rej, okres: okres, przejazdy: tr, prywatne: up, km: s.km, liczba: s.liczba,
           kierowcy: s.grupy.map(function (x) { return { imie: x.klucz, km: x.km, przejazdy: x.przejazdy, ostatnio: x.ostatnio }; }) };
};
API.dziennikOsoby = function (u, imie, okres) {
  wymagajAdmina_(u); okres_(okres);
  var tr = przejazdyOkresu_(okres, function (p) { return p.kierowca === imie; });
  var s = sumujPrzejazdy_(tr, 'rej'), nazwy = {};
  wszystkiePojazdy_().forEach(function (p) { nazwy[p.rej] = p.nazwa; });
  var up = wiersze_('UzytekPrywatny').filter(function (x) { return x.kierowca === imie && x.odData.indexOf(okres) === 0; }).sort(function (a, b) { return a.odData < b.odData ? 1 : -1; });
  return { imie: imie, okres: okres, przejazdy: tr, prywatne: up, km: s.km, liczba: s.liczba,
           pojazdy: s.grupy.map(function (x) { return { rej: x.klucz, nazwa: nazwy[x.klucz] || '', km: x.km, przejazdy: x.przejazdy, ostatnio: x.ostatnio }; }) };
};

/* ============ API: DANE POJAZDÓW (admin) ============ */
function termin_(data) {
  // poziom: brak | blad (po terminie) | uwaga (do ALERT_DNI) | ok
  if (!data) return { do: '', dni: null, poziom: 'brak' };
  var t = dzis_(), dni = Math.round((dt_(data) - dt_(t)) / 864e5);
  return { do: data, dni: dni, poziom: dni < 0 ? 'blad' : (dni <= CONFIG.ALERT_DNI ? 'uwaga' : 'ok') };
}
API.danePojazdow = function (u) {
  wymagajAdmina_(u);
  var t = dzis_(), rok = t.slice(0, 4), tr = wiersze_('Przejazdy'), ko = wiersze_('Koszty'), zd = wiersze_('Zdarzenia');
  return wszystkiePojazdy_().map(function (p) {
    var x = { rej: p.rej, nazwa: p.nazwa, rodzaj: p.rodzaj, paliwo: p.paliwo, aktywny: p.aktywny.toLowerCase() !== 'nie', uwagi: p.uwagi,
      licznikStart: p.licznikStart, licznik: p.licznik, kmLacznie: p.licznik - (p.licznikStart === '' ? 0 : p.licznikStart),
      polisaNr: p.polisaNr, polisaOd: p.polisaOd, zakres: p.zakres, polisa: termin_(p.polisaDo), przeglad: termin_(p.przegladDo),
      kmRok: 0, przejazdyRok: 0, kosztyRok: 0, paliwoRok: 0, litryRok: 0, ostatni: null, otwarteZgloszenia: 0, wTrasie: null };
    tr.forEach(function (r) {
      if (r.rej !== p.rej) return;
      if (r.status === 'W trakcie') { x.wTrasie = { kto: r.kierowca, od: r.start }; return; }
      if (r.data.slice(0, 4) === rok) { x.kmRok += r.km; x.przejazdyRok++; }
      if (!x.ostatni || r.data > x.ostatni.data) x.ostatni = { data: r.data, kierowca: r.kierowca };
    });
    ko.forEach(function (k) {
      if (k.rej !== p.rej || k.data.slice(0, 4) !== rok) return;
      x.kosztyRok += k.kwota;
      if (k.typ === 'Paliwo') { x.paliwoRok += k.kwota; if (k.ilosc !== '') x.litryRok += k.ilosc; }
    });
    x.kosztyRok = Math.round(x.kosztyRok * 100) / 100; x.paliwoRok = Math.round(x.paliwoRok * 100) / 100;
    zd.forEach(function (z) { if (z.rej === p.rej && z.status !== 'Zamknięte') x.otwarteZgloszenia++; });
    return x;
  });
};

API.zapiszPojazd = function (u, d) {
  wymagajAdmina_(u);
  var rej = tekst_(d.rej).toUpperCase();
  if (!rej) throw new Error('Wpisz numer rejestracyjny.');
  if (!tekst_(d.nazwa)) throw new Error('Wpisz markę i model.');
  ['polisaOd', 'polisaDo', 'przegladDo'].forEach(function (k) {
    var v = tekst_(d[k]); if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new Error('Data „' + k + '” ma zły format.');
  });
  if (tekst_(d.polisaOd) && tekst_(d.polisaDo) && d.polisaOd > d.polisaDo) throw new Error('Początek polisy jest po jej końcu.');
  var start = (d.licznikStart === '' || d.licznikStart === undefined || d.licznikStart === null) ? 0 : Math.round(liczba_(d.licznikStart, 'Licznik początkowy'));
  var oryginal = tekst_(d.oryginalnaRej).toUpperCase();
  if (oryginal && oryginal !== rej) throw new Error('Numeru rejestracyjnego istniejącego pojazdu nie zmienia się (zmieniłoby to historię przejazdów). Dodaj nowy pojazd.');
  var istn = null; wiersze_('Pojazdy').forEach(function (p) { if (p.rej.toUpperCase() === rej) istn = p; });
  if (istn && !oryginal) throw new Error('Pojazd o numerze ' + rej + ' już istnieje. Edytuj go na liście.');
  var o = istn || {}, przed = istn ? JSON.stringify(istn) : '';
  o.rej = rej; o.nazwa = tekst_(d.nazwa); o.rodzaj = tekst_(d.rodzaj); o.paliwo = tekst_(d.paliwo); o.licznikStart = start;
  o.polisaNr = tekst_(d.polisaNr); o.polisaOd = tekst_(d.polisaOd); o.polisaDo = tekst_(d.polisaDo); o.zakres = tekst_(d.zakres);
  o.przegladDo = tekst_(d.przegladDo); o.aktywny = d.aktywny === false ? 'nie' : 'tak'; o.uwagi = tekst_(d.uwagi);
  if (istn) zapisz_('Pojazdy', o); else dodaj_('Pojazdy', o);
  dziennik_(u.imie, rej, istn ? 'edycja pojazdu' : 'nowy pojazd', przed.slice(0, 400), '', '');
  return true;
};

/* ============ WEJŚCIE ============ */
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var req = JSON.parse(e.postData.contents);
    var u = uzytkownik_(String(req.k || '').toLowerCase());
    if (!API.hasOwnProperty(req.fn)) throw new Error('Nieznana funkcja.');
    var wynik = API[req.fn].apply(null, [u].concat(req.args || []));
    return json_({ ok: true, result: wynik });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err).replace(/^Error: /, '') });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}
function doGet() { return ContentService.createTextOutput('Ewidencja pojazdów RM — API działa.'); }
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

/* ============ MENU W ARKUSZU ============ */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Pojazdy')
    .addItem('Przygotuj arkusze (pierwsze uruchomienie)', 'przygotuj')
    .addItem('Wygeneruj klucze brakującym osobom', 'generujKlucze')
    .addItem('Odśwież zakładkę Linki', 'odswiezLinki')
    .addItem('Unieważnij link osoby…', 'uniewaznKlucz')
    .addSeparator()
    .addItem('Raport miesiąca: ewidencja przebiegu i użytek prywatny…', 'raportMiesiaca')
    .addToUi();
}
function przygotuj() {
  Object.keys(TAB).forEach(function (n) { tab_(n); });
  var us = tab_('Ustawienia');
  if (us.getLastRow() < 2) {
    var w = [['APP_URL', CONFIG.APP_URL, 'Adres aplikacji (kończy się na /pojazdy/)']];
    us.getRange(2, 1, w.length, 3).setValues(w);
  }
  var kier = tab_('Kierowcy');
  if (kier.getLastRow() < 2) kier.getRange(2, 1, 1, 3).setValues([['Imię Nazwisko', 'admin', 'tak']]);
  SpreadsheetApp.getUi().alert('Gotowe. Uzupełnij zakładki Pojazdy i Kierowcy, potem wybierz „Wygeneruj klucze”.');
}
function losowyKlucz_() {
  var s = ''; for (var i = 0; i < 4; i++) s += Utilities.getUuid().replace(/-/g, ''); return s.slice(0, 64);
}
function generujKlucze() {
  var n = 0;
  wiersze_('Kierowcy').forEach(function (k) { if (k.imie && !k.klucz) { k.klucz = losowyKlucz_(); if (!k.aktywny) k.aktywny = 'tak'; if (!k.rola) k.rola = 'kierowca'; zapisz_('Kierowcy', k); n++; } });
  odswiezLinki();
  SpreadsheetApp.getUi().alert('Nowych kluczy: ' + n + '. Linki i kody QR są w zakładce Linki.');
}
function odswiezLinki() {
  var s = ss_().getSheetByName('Linki') || ss_().insertSheet('Linki');
  s.clear();
  var app = ustawienie_('APP_URL', CONFIG.APP_URL);
  s.getRange(1, 1, 1, 4).setValues([['Imię', 'Link do aplikacji', 'Klucz', 'Kod QR']]).setFontWeight('bold');
  var w = wiersze_('Kierowcy').filter(function (k) { return k.imie && k.klucz; });
  w.forEach(function (k, i) {
    var link = app + (app.indexOf('?') >= 0 ? '&' : '?') + 'k=' + k.klucz;
    s.getRange(i + 2, 1, 1, 3).setValues([[k.imie, link, k.klucz]]);
    s.getRange(i + 2, 4).setFormula('=IMAGE("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="&ENCODEURL(B' + (i + 2) + '))');
    s.setRowHeight(i + 2, 110);
  });
  s.setColumnWidth(2, 380); s.setColumnWidth(3, 200); s.setColumnWidth(4, 120);
}
function uniewaznKlucz() {
  var ui = SpreadsheetApp.getUi(), r = ui.prompt('Unieważnij link', 'Imię i nazwisko osoby (dokładnie jak w zakładce Kierowcy):', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  var ok = false;
  wiersze_('Kierowcy').forEach(function (k) { if (k.imie === r.getResponseText().trim()) { k.klucz = losowyKlucz_(); zapisz_('Kierowcy', k); ok = true; } });
  odswiezLinki();
  ui.alert(ok ? 'Nowy klucz wygenerowany. Stary link przestał działać.' : 'Nie znaleziono takiej osoby.');
}

/* ============ RAPORT MIESIĄCA (do wydruku / księgowości / art. 86a VAT) ============ */
function raportMiesiaca() {
  var ui = SpreadsheetApp.getUi(), r = ui.prompt('Raport miesiąca', 'Miesiąc w formacie RRRR-MM (np. ' + dzis_().slice(0, 7) + '):', ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return;
  var mies = r.getResponseText().trim();
  if (!/^\d{4}-\d{2}$/.test(mies)) { ui.alert('Zły format miesiąca.'); return; }
  var nazwa = 'Raport ' + mies, s = ss_().getSheetByName(nazwa) || ss_().insertSheet(nazwa);
  s.clear();
  var wiersz = 1;
  var tr = wiersze_('Przejazdy').filter(function (p) { return p.data.slice(0, 7) === mies && p.status === 'Zakończony'; });
  var wgPoj = {}; tr.forEach(function (p) { (wgPoj[p.rej] = wgPoj[p.rej] || []).push(p); });
  Object.keys(wgPoj).sort().forEach(function (rej) {
    var l = wgPoj[rej].sort(function (a, b) { return (a.data + a.start) < (b.data + b.start) ? -1 : 1; }), suma = 0;
    s.getRange(wiersz, 1).setValue('EWIDENCJA PRZEBIEGU POJAZDU ' + rej + ' — ' + mies).setFontWeight('bold'); wiersz++;
    s.getRange(wiersz, 1, 1, 12).setValues([['Nr', 'Data', 'Kierowca', 'Licznik przed', 'Licznik po', 'Skąd', 'Dokąd', 'Trasa', 'Cel wyjazdu', 'Km', 'Zatwierdził', 'Uwagi']]).setFontWeight('bold'); wiersz++;
    var dane = l.map(function (p) { suma += p.km; return [p.nr, p.data, p.kierowca, p.licznikPrzed, p.licznikPo, p.skad, p.dokad, p.trasa, p.cel, p.km, p.zatwierdzil, p.flaga + (p.uwagi ? ' | ' + p.uwagi : '')]; });
    s.getRange(wiersz, 1, dane.length, 12).setValues(dane); wiersz += dane.length;
    s.getRange(wiersz, 9, 1, 2).setValues([['Razem:', suma]]).setFontWeight('bold'); wiersz += 2;
  });
  var up = wiersze_('UzytekPrywatny').filter(function (p) { return p.odData.slice(0, 7) === mies; }).sort(function (a, b) { return a.odData < b.odData ? -1 : 1; });
  if (up.length) {
    s.getRange(wiersz, 1).setValue('UŻYTEK PRYWATNY POJAZDÓW — ' + mies).setFontWeight('bold'); wiersz++;
    s.getRange(wiersz, 1, 1, 10).setValues([['Pojazd', 'Kto', 'Zabrano', 'Zdano', 'Licznik przed', 'Licznik po', 'Km', 'Paliwo do pełna', 'Kraj', 'Zgoda']]).setFontWeight('bold'); wiersz++;
    s.getRange(wiersz, 1, up.length, 10).setValues(up.map(function (p) { return [p.rej, p.kierowca, p.odData, p.doData, p.licznikPrzed, p.licznikPo, p.km, p.paliwoPelne, p.kraj, p.zgoda]; }));
  }
  ui.alert('Raport gotowy w zakładce „' + nazwa + '”.');
}
