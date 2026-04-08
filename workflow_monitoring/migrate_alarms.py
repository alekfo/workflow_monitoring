import sqlite3

with sqlite3.connect('alarm_base.db') as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alarm_info ")
    old_rows = cursor.fetchall()

# Вставляем в новую БД
with sqlite3.connect('db.sqlite3') as conn_new:
    cursor_new = conn_new.cursor()
    # Удаляем существующие данные, если хотим полностью заменить (осторожно!)
    # cursor_new.execute("DELETE FROM signal1520_alarm_info")  # раскомментировать при необходимости
    cursor_new.executemany(
        "INSERT OR IGNORE INTO signal1520_alarminfo (number, description, explanation) VALUES (?, ?, ?)",
        old_rows
    )
    conn_new.commit()
    print(f"Вставлено {cursor_new.rowcount} записей")

print("Готово!")