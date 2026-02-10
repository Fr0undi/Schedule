document.addEventListener("DOMContentLoaded", function () {
    // Telegram WebApp SDK
    if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
    }

    // Переключение табов (чёт/нечёт)
    const tabs = document.querySelectorAll(".tab");
    const weekContents = document.querySelectorAll(".week-content");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            const target = this.dataset.week;

            tabs.forEach(function (t) { t.classList.remove("active"); });
            this.classList.add("active");

            weekContents.forEach(function (wc) {
                wc.classList.toggle("active", wc.dataset.week === target);
            });
        });
    });

    // Аккордеон: раскрытие/сворачивание дней
    document.querySelectorAll(".day-header").forEach(function (header) {
        header.addEventListener("click", function () {
            this.parentElement.classList.toggle("open");
        });
    });
});
