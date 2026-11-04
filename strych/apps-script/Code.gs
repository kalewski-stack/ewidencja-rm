/* Strych — domowy bank garderoby (backend: Google Apps Script powiązany z arkuszem).
   Protokół jak w pozostałych ewidencjach: POST text/plain {k: kod domu, kto: id domownika, fn: nazwa, args: [...]}
   -> {ok, result} | {ok:false, error}.
   Wdrożenie: Wdróż -> Nowe wdrożenie -> Aplikacja internetowa (Wykonaj jako: Ja, Dostęp: Każdy). */

var CONFIG = {
  APP_URL: '',                 // adres aplikacji, np. https://LOGIN.github.io/ewidencja-rm/strych/  (może też być w Ustawieniach, klucz APP_URL)
  STREFA: 'Europe/Warsaw',
  PRZEGLAD_DNI_PRZED: 14,      // od ilu dni przed terminem worek pojawia się jako „wkrótce”
  ZALEGA_MIES: 12,             // worek bez żadnego przeglądu dłużej niż tyle miesięcy = „zalega”
  MAX_ZDJEC: 4,
  TAGI: ['Wiosna', 'Lato', 'Jesień', 'Zima', 'Cały rok', 'Wyrośnięte', 'Do oddania', 'Firany', 'Pościel', 'Materiały', 'Koce', 'Inne domowe'],
  RODZAJE: ['Odzież', 'Obuwie', 'Dom'],
  POJEMNIKI: ['Małe', 'Średnie', 'Duże'],
  POJEMNIKI_OPIS: { 'Małe': 'pudełko ok. 30 l', 'Średnie': 'pudełko ok. 60 l', 'Duże': 'pudełko ok. 100 l' },
  // rokUr = rok urodzenia (wiek liczy się sam); rozmiary startowe wg orientacyjnej tabeli wzrostu, do poprawienia w aplikacji
  DOMYSLNI: [
    { imie: 'Jurek', rola: 'osoba' }, { imie: 'Ania', rola: 'osoba' }, { imie: 'Marysia', rola: 'osoba' }, { imie: 'Piotr', rola: 'osoba' },
    { imie: 'Tosia', rola: 'osoba', rokUr: 2013, ubr: '158', buty: '38' }, { imie: 'Julek', rola: 'osoba', rokUr: 2013, ubr: '158', buty: '38' },
    { imie: 'Misia', rola: 'osoba', rokUr: 2015, ubr: '146', buty: '36' }, { imie: 'Gabi', rola: 'osoba', rokUr: 2024, ubr: '92', buty: '23' },
    { imie: 'Dom (wspólne)', rola: 'wspolne' }],
  KOLORY: ['#E87229', '#3B7EA1', '#6B8E4E', '#B5527A', '#8A6BBE', '#C9A227', '#2F9C95', '#7A7A7A']
};

var TAB = {
  Worki:      [['id','t'],['status','t'],['dla','t'],['rozmiar','t'],['tagi','t'],['czekaNa','t'],['strefa','t'],['polka','t'],['opis','t'],['zdjecia','t'],['wstawiono','t'],['przegladDo','t'],['przejrzano','t'],['zdjeto','t'],['dodal','t'],['zmieniono','t'],['rodzaj','t'],['rozmiarOd','t'],['rozmiarDo','t'],['pojemnik','t'],['rzeczy','t']],
  Domownicy:  [['id','t'],['imie','t'],['kolor','t'],['email','t'],['rokUr','t'],['rola','t'],['rozmiarUbr','t'],['rozmiarButy','t'],['rozmiarData','t']],
  Strefy:     [['id','t'],['nazwa','t'],['x','n'],['y','n'],['w','n'],['h','n'],['polek','n']],
  Ustawienia: [['klucz','t'],['wartosc','t'],['opis','t']],
  Dziennik:   [['kiedy','t'],['kto','t'],['worek','t'],['akcja','t'],['szczegoly','t']]
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
  return s.getRange(2, 1, n - 1, def.length).getValues().map(function (r, i) {
    var o = { _r: i + 2 };
    def.forEach(function (d, j) { var x = r[j]; o[d[0]] = (d[1] === 'n') ? (x === '' ? 0 : Number(x)) : (x === null || x === undefined ? '' : String(x)); });
    return o;
  });
}
function wartosci_(nazwa, o) { return TAB[nazwa].map(function (d) { return o[d[0]] === undefined ? '' : o[d[0]]; }); }
function dodaj_(nazwa, o) {
  var s = tab_(nazwa), r = s.getLastRow() + 1;
  s.getRange(r, 1, 1, TAB[nazwa].length).setValues([wartosci_(nazwa, o)]);
  o._r = r; return o;
}
function zapisz_(nazwa, o) { tab_(nazwa).getRange(o._r, 1, 1, TAB[nazwa].length).setValues([wartosci_(nazwa, o)]); }
function zastap_(nazwa, lista) {          // podmienia całą zawartość zakładki (strefy, domownicy)
  var s = tab_(nazwa), n = s.getLastRow();
  if (n > 1) s.getRange(2, 1, n - 1, TAB[nazwa].length).clearContent();
  if (lista.length) s.getRange(2, 1, lista.length, TAB[nazwa].length).setValues(lista.map(function (o) { return wartosci_(nazwa, o); }));
}
function ustawienie_(klucz, domyslna) {
  var w = wiersze_('Ustawienia');
  for (var i = 0; i < w.length; i++) if (w[i].klucz === klucz && w[i].wartosc !== '') return w[i].wartosc;
  return domyslna;
}
function ustaw_(klucz, wartosc, opis) {
  var w = wiersze_('Ustawienia');
  for (var i = 0; i < w.length; i++) if (w[i].klucz === klucz) { w[i].wartosc = String(wartosc); zapisz_('Ustawienia', w[i]); return; }
  dodaj_('Ustawienia', { klucz: klucz, wartosc: String(wartosc), opis: opis || '' });
}
function dziennik_(kto, worek, akcja, szczegoly) {
  dodaj_('Dziennik', { kiedy: teraz_(), kto: kto || '', worek: worek || '', akcja: akcja, szczegoly: szczegoly || '' });
}

/* ============ CZAS ============ */
function dzis_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd'); }
function teraz_() { return Utilities.formatDate(new Date(), CONFIG.STREFA, 'yyyy-MM-dd HH:mm'); }
function dt_(s) { return new Date(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10)), 12); }
function fmt_(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
function dodajDni_(s, n) { var d = dt_(s); d.setDate(d.getDate() + n); return fmt_(d); }
function dodajMies_(s, n) { var d = dt_(s), dz = d.getDate(); d.setDate(1); d.setMonth(d.getMonth() + n); var maks = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate(); d.setDate(Math.min(dz, maks)); return fmt_(d); }
function pl_(s) { return s ? s.slice(8, 10) + '.' + s.slice(5, 7) + '.' + s.slice(0, 4) : ''; }
function dataOk_(s, nazwa) {
  s = String(s || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s) || fmt_(dt_(s)) !== s) throw new Error(nazwa + ': zła data.');
  return s;
}

/* ============ AUTORYZACJA ============ */
function losowy_(n) {
  var zn = 'abcdefghjkmnpqrstuvwxyz23456789', o = '';
  for (var i = 0; i < n; i++) o += zn.charAt(Math.floor(Math.random() * zn.length));
  return o;
}
function uzytkownik_(kod, kto) {
  var wzor = String(ustawienie_('KOD', '')).toLowerCase();
  if (!wzor) throw new Error('SESJA: Arkusz nie jest przygotowany (brak kodu domu).');
  if (!kod || String(kod).toLowerCase() !== wzor) throw new Error('SESJA: Zły kod domu. Poproś domownika o aktualny link.');
  var d = wiersze_('Domownicy'), imie = '';
  for (var i = 0; i < d.length; i++) if (d[i].id === kto) imie = d[i].imie;
  return { id: kto || '', imie: imie || 'ktoś' };
}

/* ============ WALIDACJE ============ */
function tekst_(x, maks) { return String(x === null || x === undefined ? '' : x).replace(/\s+/g, ' ').trim().slice(0, maks || 200); }
function idWorka_(x) {
  x = String(x || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (!x || x.length > 8) throw new Error('Zły numer worka.');
  return /^\d+$/.test(x) ? ('000' + x).slice(-Math.max(3, x.length)) : x;
}
function lista_(s) { return String(s || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean); }

/* ============ MODEL ============ */
function domownicy_() {
  return wiersze_('Domownicy').map(function (d) {
    return { id: d.id, imie: d.imie, kolor: d.kolor, email: d.email, rokUr: d.rokUr, rola: d.rola || 'osoba', rozmiarUbr: d.rozmiarUbr, rozmiarButy: d.rozmiarButy, rozmiarData: d.rozmiarData };
  });
}
function strefy_() { return wiersze_('Strefy').map(function (z) { return { id: z.id, nazwa: z.nazwa, x: z.x, y: z.y, w: z.w, h: z.h, polek: z.polek > 0 ? z.polek : 4 }; }); }
function pojemniki_() {
  var o = {}; CONFIG.POJEMNIKI.forEach(function (p) { o[p] = ustawienie_('POJ_' + p, CONFIG.POJEMNIKI_OPIS[p]); }); return o;
}
function worekOut_(w) {
  return { id: w.id, status: w.status, dla: lista_(w.dla), rozmiar: w.rozmiar, tagi: lista_(w.tagi), czekaNa: w.czekaNa, strefa: w.strefa,
           polka: w.polka, opis: w.opis, zdjecia: lista_(w.zdjecia), rodzaj: w.rodzaj || 'Odzież', rozmiarOd: w.rozmiarOd, rozmiarDo: w.rozmiarDo, pojemnik: w.pojemnik, rzeczy: String(w.rzeczy || '').split('|').filter(Boolean), wstawiono: w.wstawiono, przegladDo: w.przegladDo,
           przejrzano: w.przejrzano, zdjeto: w.zdjeto, dodal: w.dodal, zmieniono: w.zmieniono };
}
function znajdz_(id) {
  var w = wiersze_('Worki');
  for (var i = 0; i < w.length; i++) if (w[i].id === id) return w[i];
  return null;
}

var API = {
  start: function (u) {
    return {
      dzis: dzis_(),
      domownicy: domownicy_(),
      strefy: strefy_(),
      worki: wiersze_('Worki').map(worekOut_),
      ust: {
        PLAN_SZER: Number(ustawienie_('PLAN_SZER', 6)), PLAN_DL: Number(ustawienie_('PLAN_DL', 10)),
        RZUT_ID: ustawienie_('RZUT_ID', ''), RZUT_PROP: Number(ustawienie_('RZUT_PROP', 0)), POJEMNIKI: pojemniki_(),
        KOD: ustawienie_('KOD', ''), ZALEGA_MIES: CONFIG.ZALEGA_MIES, PRZEGLAD_DNI: CONFIG.PRZEGLAD_DNI_PRZED, MAX_ZDJEC: CONFIG.MAX_ZDJEC
      }
    };
  },

  wgrajZdjecie: function (u, id, b64) {
    id = idWorka_(id);
    b64 = String(b64 || '');
    if (b64.length < 100 || b64.length > 4 * 1024 * 1024) throw new Error('Zdjęcie jest puste albo za duże.');
    var plik = folder_().createFile(Utilities.newBlob(Utilities.base64Decode(b64), 'image/jpeg', 'worek-' + id + '-' + dzis_() + '-' + losowy_(4) + '.jpg'));
    plik.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return plik.getId();
  },

  zapiszWorek: function (u, o) {
    var id = idWorka_(o.id), dla = (o.dla || []).map(String), zdj = (o.zdjecia || []).map(String);
    var znaneOsoby = domownicy_().map(function (d) { return d.id; });
    dla.forEach(function (x) { if (znaneOsoby.indexOf(x) < 0) throw new Error('Nieznany domownik.'); });
    if (!dla.length) throw new Error('Wskaż, dla kogo są te ubrania.');
    if (!zdj.length) throw new Error('Dodaj przynajmniej jedno zdjęcie.');
    if (zdj.length > CONFIG.MAX_ZDJEC) throw new Error('Maksymalnie ' + CONFIG.MAX_ZDJEC + ' zdjęcia.');
    zdj.forEach(function (x) { if (!/^[A-Za-z0-9_-]{10,80}$/.test(x)) throw new Error('Zły identyfikator zdjęcia.'); });
    var tagi = (o.tagi || []).filter(function (t) { return CONFIG.TAGI.indexOf(t) >= 0; });
    var czekaNa = o.czekaNa ? String(o.czekaNa) : '';
    if (czekaNa && znaneOsoby.indexOf(czekaNa) < 0) throw new Error('Nieznany domownik w polu „czeka na”.');
    var rodzaj = CONFIG.RODZAJE.indexOf(o.rodzaj) >= 0 ? o.rodzaj : 'Odzież';
    var pojemnik = CONFIG.POJEMNIKI.indexOf(o.pojemnik) >= 0 ? o.pojemnik : '';
    var od = tekst_(o.rozmiarOd, 8), doo = tekst_(o.rozmiarDo, 8);
    if (od && !doo) doo = od; if (doo && !od) od = doo;
    var rzeczy = [];
    (o.rzeczy || []).forEach(function (x) { x = tekst_(String(x).replace(/\|/g, ' '), 60); if (x && rzeczy.indexOf(x) < 0) rzeczy.push(x); });
    if (rzeczy.length > 40) throw new Error('Maksymalnie 40 pojedynczych rzeczy w worku.');
    var strefa = o.strefa ? String(o.strefa) : '';
    if (strefa && strefy_().filter(function (z) { return z.id === strefa; }).length === 0) throw new Error('Nieznana strefa strychu.');
    var przegladDo = o.przegladDo ? dataOk_(o.przegladDo, 'Przypomnienie') : '';

    var w = znajdz_(id), nowy = !w || w.status !== 'strych';
    var pola = { id: id, status: 'strych', dla: dla.join(','), rozmiar: od ? (od === doo ? od : od + '–' + doo) : '', rodzaj: rodzaj, rozmiarOd: od, rozmiarDo: doo, pojemnik: pojemnik, rzeczy: rzeczy.join('|'), tagi: tagi.join(','), czekaNa: czekaNa,
                 strefa: strefa, polka: tekst_(o.polka, 20), opis: tekst_(o.opis, 400), zdjecia: zdj.join(','), przegladDo: przegladDo,
                 dodal: u.imie, zmieniono: teraz_() };
    if (!w) {
      pola.wstawiono = dzis_(); pola.przejrzano = ''; pola.zdjeto = '';
      dodaj_('Worki', pola);
      dziennik_(u.imie, id, 'wstawiony', pola.dla);
    } else {
      var przed = w.dla + '|' + w.strefa + '|' + w.polka;
      if (w.status !== 'strych') { pola.wstawiono = dzis_(); pola.przejrzano = ''; pola.zdjeto = ''; }   // etykieta użyta ponownie
      else { pola.wstawiono = w.wstawiono; pola.przejrzano = w.przejrzano; pola.zdjeto = ''; }
      pola._r = w._r;
      zapisz_('Worki', pola);
      dziennik_(u.imie, id, nowy ? 'wstawiony ponownie' : 'zmieniony', przed + ' -> ' + pola.dla + '|' + pola.strefa + '|' + pola.polka);
    }
    return worekOut_(znajdz_(id));
  },

  przejrzane: function (u, id, nowaData) {
    id = idWorka_(id);
    var w = znajdz_(id); if (!w) throw new Error('Nie ma takiego worka.');
    w.przejrzano = dzis_();
    w.przegladDo = nowaData ? dataOk_(nowaData, 'Przypomnienie') : '';
    w.zmieniono = teraz_();
    zapisz_('Worki', w);
    dziennik_(u.imie, id, 'przejrzany', 'następny: ' + (w.przegladDo || 'brak'));
    return worekOut_(w);
  },

  zdejmij: function (u, id) {
    id = idWorka_(id);
    var w = znajdz_(id); if (!w) throw new Error('Nie ma takiego worka.');
    w.status = 'zdjete'; w.zdjeto = dzis_(); w.przegladDo = ''; w.zmieniono = teraz_();
    zapisz_('Worki', w);
    dziennik_(u.imie, id, 'zdjęty ze strychu', '');
    return worekOut_(w);
  },

  usun: function (u, id) {
    id = idWorka_(id);
    var w = znajdz_(id); if (!w) return true;
    tab_('Worki').deleteRow(w._r);
    dziennik_(u.imie, id, 'usunięty', w.dla);
    return true;
  },

  zapiszStrefy: function (u, lista) {
    if (!Array.isArray(lista) || lista.length > 40) throw new Error('Zbyt wiele stref.');
    var wyn = lista.map(function (z) {
      var o = { id: /^[a-z0-9]{3,12}$/.test(String(z.id)) ? String(z.id) : 's' + losowy_(5), nazwa: tekst_(z.nazwa, 40), x: Number(z.x), y: Number(z.y), w: Number(z.w), h: Number(z.h), polek: Math.max(1, Math.min(10, Math.round(Number(z.polek) || 4))) };
      if (!o.nazwa) throw new Error('Strefa musi mieć nazwę.');
      ['x', 'y', 'w', 'h'].forEach(function (k) { if (isNaN(o[k]) || o[k] < 0 || o[k] > 100) throw new Error('Zły wymiar strefy.'); o[k] = Math.round(o[k] * 10) / 10; });
      return o;
    });
    zastap_('Strefy', wyn);
    dziennik_(u.imie, '', 'plan strychu', wyn.length + ' stref');
    return strefy_();
  },

  zapiszDomownikow: function (u, lista) {
    if (!Array.isArray(lista) || !lista.length || lista.length > 16) throw new Error('Lista domowników: od 1 do 16 osób.');
    var stare = domownicy_(), uzyte = {};
    wiersze_('Worki').forEach(function (w) { lista_(w.dla).concat(w.czekaNa ? [w.czekaNa] : []).forEach(function (x) { uzyte[x] = true; }); });
    var wyn = lista.map(function (d, i) {
      var o = { id: /^d[a-z0-9]{3,10}$/.test(String(d.id)) ? String(d.id) : 'd' + losowy_(5), imie: tekst_(d.imie, 30),
                kolor: /^#[0-9A-Fa-f]{6}$/.test(String(d.kolor)) ? String(d.kolor) : CONFIG.KOLORY[i % CONFIG.KOLORY.length], email: tekst_(d.email, 80),
                rokUr: '', rola: d.rola === 'wspolne' ? 'wspolne' : 'osoba', rozmiarUbr: tekst_(d.rozmiarUbr, 8), rozmiarButy: tekst_(d.rozmiarButy, 8), rozmiarData: '' };
      if (!o.imie) throw new Error('Każdy domownik musi mieć imię.');
      if (d.rokUr !== '' && d.rokUr !== undefined && d.rokUr !== null) {
        var r = Number(d.rokUr); if (!(r >= 1900 && r <= Number(dzis_().slice(0, 4)))) throw new Error(o.imie + ': zły rok urodzenia.');
        o.rokUr = String(r);
      }
      var st = stare.filter(function (x) { return x.id === o.id; })[0];
      var zmiana = !st || st.rozmiarUbr !== o.rozmiarUbr || st.rozmiarButy !== o.rozmiarButy;
      o.rozmiarData = (zmiana && (o.rozmiarUbr || o.rozmiarButy)) ? dzis_() : (st ? st.rozmiarData : '');
      return o;
    });
    var ids = wyn.map(function (d) { return d.id; });
    stare.forEach(function (d) { if (ids.indexOf(d.id) < 0 && uzyte[d.id]) throw new Error(d.imie + ' ma przypisane worki. Najpierw zmień w nich osobę.'); });
    zastap_('Domownicy', wyn);
    dziennik_(u.imie, '', 'domownicy', wyn.length + ' osób');
    return domownicy_();
  },

  ustawRzut: function (u, id, prop) {
    if (id && !/^[A-Za-z0-9_-]{10,80}$/.test(String(id))) throw new Error('Zły identyfikator pliku.');
    prop = Number(prop);
    if (id && !(prop > 0.2 && prop < 5)) throw new Error('Zły stosunek boków rzutu.');
    ustaw_('RZUT_ID', id || '', 'zdjęcie rzutu strychu (tło planu)');
    ustaw_('RZUT_PROP', id ? Math.round(prop * 1000) / 1000 : 0, 'wysokość / szerokość rzutu');
    dziennik_(u.imie, '', 'rzut strychu', id ? 'ustawiony' : 'usunięty');
    return { RZUT_ID: id || '', RZUT_PROP: id ? prop : 0 };
  },

  ustawPojemniki: function (u, opisy) {
    CONFIG.POJEMNIKI.forEach(function (p) { ustaw_('POJ_' + p, tekst_(opisy[p], 60) || CONFIG.POJEMNIKI_OPIS[p], 'opis pojemnika: ' + p); });
    return pojemniki_();
  },

  ustawPlan: function (u, szer, dl) {
    szer = Number(String(szer).replace(',', '.')); dl = Number(String(dl).replace(',', '.'));
    if (!(szer >= 1 && szer <= 50 && dl >= 1 && dl <= 50)) throw new Error('Wymiary w metrach, od 1 do 50.');
    ustaw_('PLAN_SZER', szer, 'szerokość strychu w metrach (tylko proporcje planu)');
    ustaw_('PLAN_DL', dl, 'długość strychu w metrach (tylko proporcje planu)');
    return { PLAN_SZER: szer, PLAN_DL: dl };
  }
};
var ZAPISY = { ustawRzut: 1, ustawPojemniki: 1, wgrajZdjecie: 1, zapiszWorek: 1, przejrzane: 1, zdejmij: 1, usun: 1, zapiszStrefy: 1, zapiszDomownikow: 1, ustawPlan: 1 };

function folder_() {
  var id = ustawienie_('FOLDER_ID', '');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  var f = DriveApp.createFolder('Strych — zdjęcia worków');
  ustaw_('FOLDER_ID', f.getId(), 'folder Dysku Google ze zdjęciami (nie usuwaj)');
  return f;
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    var req = JSON.parse(e.postData.contents);
    var u = uzytkownik_(req.k, req.kto);
    if (!API.hasOwnProperty(req.fn)) throw new Error('Nieznana funkcja.');
    if (ZAPISY[req.fn]) lock.waitLock(20000);
    var wynik = API[req.fn].apply(null, [u].concat(req.args || []));
    return json_({ ok: true, result: wynik });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err).replace(/^Error: /, '') });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}
function doGet() { return ContentService.createTextOutput('Strych — API działa.'); }
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

/* ============ MENU W ARKUSZU ============ */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Strych')
    .addItem('Przygotuj arkusze (pierwsze uruchomienie)', 'przygotuj')
    .addItem('Pokaż kod domu i link', 'pokazLink')
    .addItem('Wygeneruj nowy kod domu', 'nowyKod')
    .addSeparator()
    .addItem('Włącz przypomnienia e-mail (poniedziałek rano)', 'wlaczPrzypomnienia')
    .addItem('Wyłącz przypomnienia e-mail', 'wylaczPrzypomnienia')
    .addItem('Wyślij przypomnienie teraz', 'przypomnijTydzien')
    .addToUi();
}
function przygotuj() {
  Object.keys(TAB).forEach(tab_);
  if (!ustawienie_('KOD', '')) ustaw_('KOD', losowy_(10), 'kod domu: wpisuje się go raz na telefonie (lub jest w linku)');
  ustaw_('APP_URL', ustawienie_('APP_URL', CONFIG.APP_URL), 'adres aplikacji (GitHub Pages), z ukośnikiem na końcu');
  if (!wiersze_('Domownicy').length) {
    zastap_('Domownicy', CONFIG.DOMYSLNI.map(function (d, i) {
      return { id: 'd' + losowy_(5), imie: d.imie, kolor: CONFIG.KOLORY[i % CONFIG.KOLORY.length], email: '', rokUr: d.rokUr ? String(d.rokUr) : '', rola: d.rola,
               rozmiarUbr: d.ubr || '', rozmiarButy: d.buty || '', rozmiarData: d.ubr ? dzis_() : '' };
    }));
  }
  folder_();
  SpreadsheetApp.getUi().alert('Gotowe. Imiona domowników zmienisz w aplikacji (Ustawienia) albo w zakładce Domownicy.\nKod domu: ' + ustawienie_('KOD', '') + '\nLink do aplikacji z kodem: Strych → Pokaż kod domu i link.');
}
function adresApp_() { return ustawienie_('APP_URL', CONFIG.APP_URL); }
function pokazLink() {
  var url = adresApp_();
  SpreadsheetApp.getUi().alert('Kod domu: ' + ustawienie_('KOD', '') + '\n\nLink do wysłania domownikom (instaluje się jednym kliknięciem):\n' + (url ? url + '?k=' + ustawienie_('KOD', '') : '(wpisz APP_URL w zakładce Ustawienia)'));
}
function nowyKod() {
  var ui = SpreadsheetApp.getUi();
  if (ui.alert('Nowy kod domu', 'Stare linki i zapisane kody przestaną działać. Każdy domownik wpisze nowy kod (albo otworzy nowy link). Kontynuować?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  ustaw_('KOD', losowy_(10), 'kod domu');
  pokazLink();
}

/* ============ PRZYPOMNIENIA E-MAIL ============ */
var SEZONY_OKNA = { 'Wiosna': ['03-01', '05-31'], 'Lato': ['06-01', '08-31'], 'Jesień': ['09-01', '11-30'], 'Zima': ['12-01', '02-end'] };
// Sezony z tagów worka, które w całości minęły od ostatniego ruchu (wstawienia albo przeglądu): worek nie został podjęty.
function przegapione_(w, d) {
  var ost = w.przejrzano || w.wstawiono, wyn = [];
  if (!ost) return wyn;
  Object.keys(SEZONY_OKNA).forEach(function (n) {
    if (lista_(w.tagi).indexOf(n) < 0) return;
    for (var y = Number(d.slice(0, 4)); y >= Number(ost.slice(0, 4)) - 1; y--) {
      var a = y + '-' + SEZONY_OKNA[n][0], ry = n === 'Zima' ? y + 1 : y;
      var b = SEZONY_OKNA[n][1] === '02-end' ? ry + '-02-' + new Date(ry, 2, 0).getDate() : ry + '-' + SEZONY_OKNA[n][1];
      if (a >= ost && b < d) { wyn.push(n + ' ' + (n === 'Zima' ? y + '/' + String(ry).slice(2) : y)); return; }
    }
  });
  return wyn;
}
function przypomnijTydzien() {
  var d = dzis_(), prog = dodajDni_(d, CONFIG.PRZEGLAD_DNI_PRZED), zalega = dodajMies_(d, -CONFIG.ZALEGA_MIES);
  var osoby = {}; domownicy_().forEach(function (x) { osoby[x.id] = x; });
  var adresy = domownicy_().map(function (x) { return x.email; }).filter(Boolean);
  if (!adresy.length) { try { SpreadsheetApp.getUi().alert('Brak adresów e-mail w zakładce Domownicy.'); } catch (e) {} return; }
  var url = adresApp_(), wiersze = [];
  wiersze_('Worki').forEach(function (w) {
    if (w.status !== 'strych') return;
    var powody = [];
    if (w.przegladDo && w.przegladDo <= d) powody.push('termin minął ' + pl_(w.przegladDo));
    else if (w.przegladDo && w.przegladDo <= prog) powody.push('termin ' + pl_(w.przegladDo));
    var ost = w.przejrzano || w.wstawiono;
    if (ost && ost < zalega) powody.push('nikt nie zaglądał od ' + pl_(ost));
    przegapione_(w, d).forEach(function (x) { powody.push('minął sezon ' + x + ', a worek nie był ruszany'); });
    if (!powody.length) return;
    var dla = lista_(w.dla).map(function (x) { return osoby[x] ? osoby[x].imie : '?'; }).join(', ');
    wiersze.push('<li><a href="' + url + '#/w/' + w.id + '"><b>#' + w.id + '</b></a> — ' + dla + (w.rozmiar ? ', ' + w.rozmiar : '') + ' (' + powody.join('; ') + ')</li>');
  });
  if (!wiersze.length) return;
  MailApp.sendEmail({
    to: adresy.join(','),
    subject: 'Strych: ' + wiersze.length + ' ' + (wiersze.length === 1 ? 'worek do przeglądu' : 'worków do przeglądu'),
    htmlBody: '<p>Te worki czekają na decyzję (wymiana, przegląd albo oddanie):</p><ul>' + wiersze.join('') + '</ul><p><a href="' + url + '">Otwórz Strych</a></p>'
  });
}
function wlaczPrzypomnienia() {
  wylaczPrzypomnienia();
  ScriptApp.newTrigger('przypomnijTydzien').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(8).create();
  SpreadsheetApp.getUi().alert('Włączone. Co poniedziałek rano dostaniecie e-mail, jeśli jakiś worek czeka na przegląd. Adresy wpisz w zakładce Domownicy (kolumna email).');
}
function wylaczPrzypomnienia() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'przypomnijTydzien') ScriptApp.deleteTrigger(t); });
}
