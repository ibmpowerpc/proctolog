# Proctolog

Утилита делает скриншоты, отправляет их в RouterAI и показывает последний ответ
на web-странице.

## Как это выглядит

<img width="1280" height="591" alt="telegram-cloud-photo-size-2-5244732930955877065-y" src="https://github.com/user-attachments/assets/0cfad1ea-3bc5-46c1-a9f7-743cbd498a5e" />


## Установка

```sh
git clone https://github.com/ibmpowerpc/proctolog
cd proctolog
scripts/bootstrap
source .venv/bin/activate
```

Укажите API-ключ RouterAI:

```sh
export ROUTERAI_API_KEY="..."
```

На macOS дайте Terminal/iTerm доступ к записи экрана:

```text
System Settings -> Privacy & Security -> Screen Recording
```

На Linux установите одну из утилит для скриншотов:

```sh
# Wayland, wlroots/Sway/Hyprland
sudo apt install grim

# GNOME/KDE/X11
sudo apt install gnome-screenshot

# X11 fallback
sudo apt install scrot
```

Если команда скриншота нестандартная, задайте её в конфиге через
`screenshot_command`, например:

```json
{
  "screenshot_command": ["grim", "{output}"]
}
```

## Первый запуск

Создайте конфиг:

```sh
proctolog init
```

Пробный запуск без API-запроса:

```sh
proctolog run --once --dry-run
```

Один реальный запрос:

```sh
proctolog run --once
```

## Постоянная работа

Хост 1 — то устройство, на котором вы проходите тест. Хост 2 — устройство, на котором вы смотрите ответы.

На хосте 1 выполните:

```sh
cd /path/to/proctolog
source .venv/bin/activate
proctolog start
```

`start` одновременно запускает снятие скриншотов и web-страницу. Он напечатает адреса:

```text
Local URL: http://127.0.0.1:8765
LAN URL:   http://192.168.X.X:8765
```

На хосте 2 откройте `LAN URL`. Компьютер и телефон должны быть в одной Wi-Fi сети.

## Управление

На web-странице показывается только последний ответ.

Кнопка в правом нижнем углу:

- `Пауза` — сразу останавливает текущий запрос и новые скриншоты;
- `Продолжить` — сразу запускает следующий запрос.

## Настройки

Конфиг находится здесь:

```text
~/.config/proctolog/config.json
```

После изменения конфига перезапустите `proctolog start`.

## Данные

Ответы и служебные файлы пишутся сюда:

```text
~/.local/share/proctolog/
```

Там находятся:

- `events.jsonl` — лог ответов;
- `transcript.md` — читаемый transcript;
- `screenshots/` — сохранённые скриншоты;
- `state.json` — состояние утилиты.
