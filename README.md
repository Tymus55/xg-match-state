# Zadanie 1: Różnica xG według stanu meczu

Obliczenie różnicy xG (expected goals) dla każdego stanu meczu
(Zwycięstwo / Remis / Przegrana) obu drużyn w meczu Polonia Bytom vs
Pogon Grodzisk Mazowiecki, na podstawie danych zdarzeniowych StatsBomb.

## Uruchomienie

```bash
pip install -r requirements.txt
python main.py
```

## Wymagania

| Pakiet | Wersja | Do czego                    |
| ------ | ------ | --------------------------- |
| Python | >= 3.9 | środowisko uruchomieniowe   |
| pandas | >= 2.0 | wczytanie i agregacja danych |

## Metoda

1. Wczytanie CSV i deduplikacja zdarzeń po kolumnie `id` (StatsBomb 360
   powiela wiersze dla każdego zawodnika w `freeze_frame`).
2. Sortowanie chronologiczne: `period`, `minute`, `second`, `timestamp`.
3. Odtworzenie bieżącego wyniku. Gol to `event_type_name == "Shot"` oraz
   `outcome_name == "Goal"`. Skumulowana suma goli dla każdej drużyny jest
   przesunięta o jedno zdarzenie (`shift(1)`), więc wynik zmienia się od
   zdarzenia *po* golu, a sam strzał bramkowy liczy się w stanie, który
   obowiązywał przed jego oddaniem.
4. Przypisanie `match_state` (Zwycięstwo / Remis / Przegrana) z perspektywy
   drużyny, której dotyczy zdarzenie.
5. Zostawienie tylko strzałów i zsumowanie `statsbomb_xg` po drużynie i stanie.
6. Różnica xG = xG drużyny w danym stanie minus xG przeciwnika w **tych samych
   okresach wyniku**. Stany są względne wobec każdej drużyny, więc przeciwnik
   bierze stan komplementarny: Zwycięstwo <-> Przegrana, Remis <-> Remis.
   Łączenie po tej samej etykiecie porównywałoby strzały z różnych fragmentów
   meczu.

## Wynik

Mecz zakończył się 2:2 (Pogon 21', Polonia 27' i 36', Pogon 45' II połowa).

| druzyna                   | stan meczu | xG druzyny | xg przeciwnika (ten sam stan) | roznica xg |
| ------------------------- | ---------- | ---------- | ----------------------------- | ---------- |
| Polonia Bytom             | Zwycięstwo | 0.066      | 0.017                         | +0.050     |
| Polonia Bytom             | Remis      | 0.923      | 0.609                         | +0.314     |
| Polonia Bytom             | Przegrana  | 0.079      | 0.117                         | -0.038     |
| Pogon Grodzisk Mazowiecki | Zwycięstwo | 0.117      | 0.079                         | +0.038     |
| Pogon Grodzisk Mazowiecki | Remis      | 0.609      | 0.923                         | -0.314     |
| Pogon Grodzisk Mazowiecki | Przegrana  | 0.017      | 0.066                         | -0.050     |

Kontrola: 34 strzały łącznie (Polonia 20, Pogon 14), sumy xG po stanach zgadzają
się z totalami drużyn (1.069 / 0.743). Liczby sprawdzone też przez sumowanie xG
bezpośrednio w oknach czasowych między golami.

## Pliki

- `main.py` - skrypt
- `Polonia Bytom_Pogo  Grodzisk Mazowiecki_4068759.csv` - dane wejściowe (StatsBomb)
- `requirements.txt` - wymagania

---

# Zadanie 2: Ocena zawodnika na wahadłowego

Pytanie: czy zawodnik X nadaje się na wahadłowego w naszym systemie, mając StatsBomb z jego 20 meczów? Jak bym do tego podszedł i gdzie te dane mnie zawiodą.

## 1. Podejście analityczne (jak ocenię zawodnika)

Wahadłowy w systemie z trójką stoperów gra na całej długości boiska. W fazie ataku musi dawać szerokość, dośrodkowania i wejścia w pole karne. W fazie obrony wraca do linii czterech, broni 1v1 i uczestniczy w pressingu. Profil, którego szukam, to balans: nie skrajny skrzydłowy z wysokim xA i słabą obroną, i nie klasyczny fullback, który rzadko przekracza połowę.

Z 20 meczów StatsBomb buduję profil w trzech warstwach: ofensywa, defensywa, przestrzeń.

Ofensywa. Progressive carries i progressive passes pokazują, czy zawodnik faktycznie przenosi grę do przodu, czy tylko utrzymuje piłkę na boku. xA z otwartej gry (bez stałych fragmentów) mówi, czy jego dośrodkowania i podania w pole karne mają realną wartość bramkową, a nie tylko wolumen. Crosses filtruję po strefie: dośrodkowanie z linii końcowej to inny profil niż z połowy boiska. Udział w xGChain i Shot-Creating Actions sprawdza, czy zawodnik regularnie pojawia się w sekwencjach kończących się strzałem, nawet gdy sam nie asystuje.

Defensywa. Skuteczność defensive duels (wygrane / wszystkie) w strefie boisku, zwłaszcza w 1v1 przy linii. Pressures i counterpressures na połowie rywala: wahadłowy w naszym systemie często jest pierwszym zawodnikiem, który zamyka szerokość po stracie. Interceptions i ball recoveries w środkowej i wysokiej trzeciej: czy czyta grę, czy tylko reaguje po dośrodkowaniu rywala.

Przestrzeń. Na współrzędnych `location_x`, `location_y` buduję heatmapę zdarzeń z piłką (i osobno: carries, pressures, crosses). Szukam dwóch rzeczy. Po pierwsze, czy zawodnik operuje na pełnej długości swojego skrzydła (wysokie wejścia + cofnięcia), czy jego gęstość kończy się w połowie boiska. Po drugie, czy heatmapa wygląda jak wahadło (szeroko, wysoko), czy jak klasyczny boczny obrońca w czwórce (głęboko, wąsko). Porównuję to z heatmapami wahadłowych z ligi / pozycji, nie z absolutnymi benchmarkami wyjętymi z kontekstu.

Na koniec normalizuję metryki na 90 minut i rozbijam po stanie meczu oraz fazie (atak pozycyjny vs kontratak). Zawodnik, który „znika” przy prowadzeniu albo nie wraca po stracie, odpada niezależnie od ładnego xA.

Werdykt z samych eventów to zawsze warunkowy: „pasuje / nie pasuje do naszego profilu wahadła *na podstawie tego, co StatsBomb rejestruje*”. Decyzję domykam dopiero po video i danych fizycznych.

## 2. Ograniczenia danych (gdzie StatsBomb mnie zawodzi)

StatsBomb (w tym 360) to event data: zdarzenia z udziałem piłki, czasem z kontekstem zawodników w kadrze w momencie strzału lub podania. To nie jest tracking data ani physical data. Różnica jest fundamentalna: event data mówi, *co zrobił piłkarz z piłką*; tracking mówi, *gdzie był i jak się poruszał przez całe 90 minut*. Na wahadle ta luka boli najbardziej.

1. Brak danych motorycznych. Wahadłowy jest jedną z najbardziej wymagających fizycznie pozycji. Z eventów nie wyciągnę dystansu w High Speed Running, liczby sprintów, powtarzalności wysiłku w drugiej połowie ani Work Rate. Zawodnik może mieć świetne progressive carries w 20 meczach i jednocześnie nie wytrzymać naszego obciążenia mecz + trening, albo spadać po 60. minucie. Tego ze StatsBomb nie zobaczę.

2. Ruch bez piłki. Event data prawie w ogóle nie rejestruje off-ball movement. Idealny overlapping run, który ściąga obrońcę i otwiera półprzestrzeń dla ósemki, nie istnieje w danych, jeśli zawodnik nie dostał podania. To samo dotyczy cofania się do linii i ustawiania przed dośrodkowaniem rywala: jeśli nie było tackle’a ani interception, w eventach go nie ma. A właśnie te przebiegi bez piłki często decydują, czy ktoś „gra jak wahadło”, czy tylko zbiera ładne liczby przy piłce.

3. Bias systemu poprzedniej drużyny. 20 meczów to próbka zachowań w konkretnym taktycznym pudełku. Jeśli X grał jako fullback w czwórce w niskim bloku, jego liczby ofensywne (crosses, xA, progressive carries w ostatniej trzeciej) będą słabe z definicji: system mu tego nie dawał. To nie znaczy, że nie poradzi sobie wyżej na wahadle przy trójce stoperów, gdzie ma więcej przestrzeni i obowiązek atakowania. Odwrotnie: skrzydłowy z wysokiego pressingu może wyglądać ofensywnie rewelacyjnie, a w naszym systemie okazać się słaby w 1v1 po cofnięciu. Event data mierzy output w danym kontekście, nie potencjał w innym. Bez video, scoutingu taktycznego i porównania ról (role continuity) łatwo odrzucić dobrego kandydata albo kupić „ładne liczby”.

Dlatego StatsBomb z 20 meczów to dobry filtr wstępny i dobre pytanie do wideo („czy te carries to naprawdę wahadło, czy izolowane dryblingi?”). Nie wystarczą do decyzji transferowej na tę pozycję. Do domknięcia potrzebuję tracking/physical (obciążenie, powtarzalność sprintów), analizy ruchu bez piłki z video oraz świadomego odfiltrowania biasu systemu, w którym zawodnik dotychczas grał.
