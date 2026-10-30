# gitpulse

**Sahip olduğun bütün repolar tek ekranda: hangisi kirli, hangisinde push edilmemiş commit var, hangisi ölü.**

[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](https://www.python.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](pyproject.toml)
[![Read-only](https://img.shields.io/badge/git-read--only-informational)](#nasıl-çalışır)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

<img src="docs/demo.svg" alt="gitpulse altı repoyu branch, son commit, değişiklikler ve senkron durumuyla gösteriyor" width="860">

Otuz proje, üçünde unuttuğun commit'lenmemiş işler, birinde push edilmemiş
commit'ler ve bahardan beri orada duran `experiment/rewrite` branch'i.

`gitpulse` bir dizini tarar, içindeki tüm git repolarını bulur ve iki saniyede
okunacak tek bir tablo basar:

```console
$ gitpulse ~/code
gitpulse 0.1.0 · 6 repos · under ~/code · 8 dirs · 0.05s

  REPO               BRANCH   LAST COMMIT                 CHANGES  SYNC  LAST  FLAGS
  -----------------  -------  --------------------------  -------  ----  ----  -------------------------
  web-app            main     fix: handle empty datasets        2    ↑2    1d  1 modified · 1 untracked
  legacy-crm         main     merge: reports                clean    ↑2   6mo  1 stale branch · 1 merged
  api-server         main     feat: health endpoint         clean    ↓1    9d  ✓
  clients/acme-site  main     feat: landing page            clean     =    4d  ✓
  design-tokens      main     feat: initial token set       clean     =   14d  ✓
  scratch            (empty)  -                                 -     -     -  ✓

  1 dirty repo · 2 unpushed repos · 1 repo behind · 1 stale branch (>30d) · 1 merged branch
  quietest: legacy-crm (189 days without a commit)
```

Ağ yok, daemon yok, ayar dosyası yok, veritabanı yok. Sadece `git` ve bir tablo.

## Neden `git status` yetmiyor?

`git status` "bu reponun durumu ne" sorusunu yanıtlar. `gitpulse` ise
"**bugün hangi repom beni bekliyor**" sorusunu yanıtlar — çok sayıda projeyle
çalışırken gerçekten sorduğun soru budur.

Ve bunu otuz dizine tek tek `cd` yaparak öğrenmek istemezsin.

## Kurulum

```console
$ pipx install gitpulse      # önerilen: izole, her zaman PATH'te
$ uv tool install gitpulse   # ya da uv ile
$ pip install gitpulse       # ya da mevcut ortama
```

Depodan:

```console
$ git clone https://github.com/OWNER/gitpulse.git
$ cd gitpulse
$ pipx install .
```

Linux ve macOS'ta Python 3.11+; Windows çalışmalı ama denenmedi. `git`'in
`PATH`'te olması gerekir.

## Kullanım

```
gitpulse [PATH ...] [seçenekler]
```

| Seçenek | Ne yapar |
| --- | --- |
| `--only FILTER` | Sadece `attention`, `dirty`, `unpushed`, `behind`, `stale`, `detached` |
| `--sort ORDER` | `attention` (varsayılan), `activity`, `name`, `changes` |
| `--stale AGE` | `AGE` boyunca commit almamış branch "bayat" sayılır (`30d`, `12h`, `2w`) |
| `--depth N` | Repoları ne kadar derinde arasın (varsayılan `4`) |
| `--jobs N` | Aynı anda kaç repo incelensin (varsayılan `8`) |
| `--exclude NAME` | Bu isimdeki dizinleri atla (tekrarlanabilir) |
| `-v`, `--verbose` | Son commit başlığı kolonunu ekler |
| `--json` | Makine okunur çıktı (cron, dashboard) |
| `--fail-on COND` | Eşleşme varsa `1` ile çık: `attention`, `dirty`, `unpushed`, `stale` |
| `--color {auto,always,never}` | Renk denetimi; `NO_COLOR` / `FORCE_COLOR` da dikkate alınır |
| `--version` | Sürümü yazar |

Çıkış kodları: `0` sorun yok, `1` `--fail-on` eşleşti veya hiçbir kök taranamadı,
`2` hatalı kullanım.

### Kolonlar

| Kolon | Anlamı |
| --- | --- |
| `REPO` | Taranan köke göre yol — `clients/acme-site` hangi `site` olduğunu netleştirir |
| `BRANCH` | Aktif branch; `(detached)` veya hiç commit yoksa `(empty)` |
| `LAST COMMIT` | Commit başlığı (sadece `-v` ile) |
| `CHANGES` | `clean` ya da staged + modified + untracked dosya sayısı |
| `SYNC` | `↑n` push edilecek, `↓n` çekilecek, `=` senkron, upstream yoksa `no up` |
| `LAST` | En yeni commit ne kadar önce atıldı |
| `FLAGS` | staged/modified/untracked dağılımı, bayat ve merge edilmiş branch'ler, `no upstream` |

Satırlar "ne kadar seni bekliyor" sırasına göre dizilir: hatalar, kirli ağaçlar,
push edilmemiş işler, geride kalan repolar, bayat branch'ler; sonra geri kalanlar
yenilik sırasına göre.

## Tarifler

```console
# sabah kahvesi: bugün beni ne bekliyor?
gitpulse ~/code --only attention

# hangi projeler sessizce öldü?
gitpulse ~/code --sort activity --only attention

# bahar temizliği: çeyrek yıldır dokunulmamış, merge edilmemiş branch'ler
gitpulse ~/code --stale 90d --only stale

# derin bir ağaçta isimle repo bulmak
gitpulse ~ --depth 6 --sort name -v | grep -i "invoice"

# dashboard ve cron işleri
gitpulse ~/code --json | jq '.totals'

# CI'da "arkanda bir şey bıraktın" kontrolü
gitpulse . --fail-on dirty
```

Kabuğa bir alias koymak hemen karşılığını verir:

```bash
alias gp='gitpulse ~/code --only attention'
```

## JSON

```console
$ gitpulse ~/code --json | jq '.totals'
{
  "repos": 6,
  "dirty": 1,
  "unpushed": 2,
  "behind": 1,
  "stale_branches": 1,
  "merged_branches": 1,
  "needs_attention": 3
}
```

Her repo nesnesi `name`, `label`, `path`, `branch`, `detached`, `empty`,
`staged`, `modified`, `untracked`, `changes`, `dirty`, `ahead`, `behind`,
`has_upstream`, `commits`, `last_commit_at`, `last_message`, `age_seconds`,
`stale_branches`, `merged_branches`, `local_branches`, `flags`,
`needs_attention` ve `error` alanlarını taşır.

## Nasıl çalışır?

- **Salt-okunur.** `gitpulse` yalnızca `rev-parse`, `status`, `rev-list`, `log`
  ve `for-each-ref` çalıştırır. Commit atmaz, stage etmez, fetch etmez, checkout
  yapmaz, hiçbir şey yazmaz. (`GIT_OPTIONAL_LOCKS=0` ile index'e bile dokunmaz.)
- **Tasarım gereği çevrimdışı.** `ahead`/`behind` yerel ref'lerine göre, son
  `git fetch`'inin durumuyla hesaplanır. Fetch ağ erişimi ve yan etki demektir;
  bir dashboard bunu arkandan yapmamalı.
- **Paralel ama nazik.** Repolar thread pool ile incelenir (`--jobs`), çünkü iş
  CPU'da değil alt süreçleri beklemekte.
- **Sınırlı arama.** Dolaşma bir repoda durur (içindeki test repoları tabloyu
  patlatmaz), `node_modules`, `.venv`, `dist`, `target` gibi dizinleri atlar ve
  `--depth` sınırına uyar.
- **Bozuk repoya dürüst.** Bozuk bir repo, tüm tabloyu öldüren bir istisna
  yerine `error` etiketli tek satır olur.

## Geliştirme

```console
$ make install     # editable kurulum + dev bağımlılıkları
$ make test        # pytest
$ make lint        # ruff check + ruff format --check
$ make demo        # docs/demo*.svg dosyalarını gerçek repolardan üretir
```

Testler geçici dizinlerde **gerçek git repoları** kurar — mock git yok, diske
gömülü fixture yok — yani test paketi senin çalıştırdığın komutların aynısını
çalıştırır.

Dizin yapısı:

```
src/gitpulse/
  git.py       salt-okunur, ince subprocess sarmalayıcı
  repos.py     keşif, repo incelemesi, paralel tarama
  model.py     değişmez RepoState anlık görüntüsü + türetilmiş etiketler
  report.py    sıralama, filtreler, tablo, özet, JSON
  ui.py        renk, kolon hizalaması, küçük formatlayıcılar
tests/         tmp_path içinde gerçek repolar, ağ yok
```

Yeni bir kolon veya kontrol eklemek istersen [CONTRIBUTING.md](CONTRIBUTING.md).

## Yol haritası

- `--fetch` (isteğe bağlı) ile rapor öncesi ahead/behind tazeleme
- submodule ve worktree farkındalığı ("bu bir repo" demenin ötesinde)
- tabloyu birkaç saniyede bir yenileyen `--watch` modu
- `gh` varsa repo başına PR/issue sayıları

## SSS

**Dışarıya veri gönderiyor mu?**
Hayır. Pakette hiç ağ kodu yok.

**Repolarımı değiştiriyor mu?**
Hayır. Yazmaz, stage etmez, commit atmaz, fetch etmez, checkout yapmaz.

**Submodule'leri takip ediyor mu?**
Submodule, repo içinde bir dizin olarak görünür; `gitpulse` üst repoyu raporlar,
içine inmez. Worktree'ler (`git worktree add`) normal repo olarak bulunur.

**`ahead`/`behind` neden güncel değil?**
Çünkü yerel görünümünü anlatıyor. Önce `git fetch` yap (ya da planlanan
`--fetch` bayrağını bekle).

**Linux, macOS, Windows?**
Linux ve macOS test edildi. Windows çalışmalı — sarmalayıcı yalnızca `git`
çağırıyor — ama test paketi orada henüz koşmuyor.

## Lisans

MIT — [LICENSE](LICENSE) dosyasına bakın.

---

<sub>English documentation: [README.md](README.md)</sub>
