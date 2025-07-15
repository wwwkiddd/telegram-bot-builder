document.getElementById("bot-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const botToken = document.getElementById("bot_token").value;
  const adminId = document.getElementById("admin_id").value;
  const result = document.getElementById("result");

  result.textContent = "Создание бота...";

  try {
    const response = await fetch("http://127.0.0.1:8080/create_bot/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bot_token: botToken,
        admin_id: parseInt(adminId)
      })
    });

    const data = await response.json();

    if (response.ok) {
      result.textContent = `✅ Бот создан! Вот ссылка: https://t.me/${getUsernameFromToken(botToken)}`;
    } else {
      result.textContent = `❌ Ошибка: ${data.detail}`;
    }
  } catch (err) {
    result.textContent = "❌ Не удалось подключиться к серверу.";
  }
});

// Быстрое извлечение username (не точное, временное)
function getUsernameFromToken(token) {
  const parts = token.split(":");
  return "your_bot"; // Можно позже заменить на запрос к Telegram API
}
