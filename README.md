# Касов дневник

Локално десктоп приложение с Python 3.11, Qt Quick и SQLite. Отвори `Стартирай.command` на macOS или стартирай `.venv/bin/python -m cash_ledger` от тази директория.

При първо отваряне базата е празна. Задай салдото преди първата операция от **Начална каса**. Полетата под таблицата записват за текущия ден. Датата над таблицата служи за преглед на записите по дни. Сумите на екрана са в евро.

На macOS записите са в `~/Library/Application Support/KasovDnevnik/cash-ledger.sqlite3`. Приложението работи без интернет. За отделна тестова база подай `--database /абсолютен/път/до/тест.sqlite3`.

## Настройка в ново копие

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m cash_ledger
```

На Windows използвай `py -3.11 -m venv .venv` и `.venv\Scripts\python.exe` вместо `.venv/bin/python`. Първата версия е проверена на macOS.

## Тестове

```sh
.venv/bin/python -m unittest discover -s tests
```

Тестовете използват временни SQLite файлове. Сред проверките са касата от примерния ден, историята, записването с Enter и предупреждението при повече от едно поле за грамаж.
