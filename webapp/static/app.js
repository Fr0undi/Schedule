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

    // Поиск
    var searchBox = document.querySelector(".search-box");
    var noResults = document.querySelector(".no-results");
    var searchResults = document.querySelector(".search-results");
    var instituteList = document.querySelector(".institute-list");
    var searchItems = document.querySelectorAll(".search-item");

    function normalize(text) {
        return text.replace(/[\s\-]+/g, "").toLowerCase();
    }

    if (searchBox && searchItems.length) {
        searchBox.addEventListener("input", function () {
            var query = normalize(this.value);

            if (!query) {
                // Пустой поиск — показать иерархию
                searchResults.style.display = "none";
                instituteList.style.display = "";
                noResults.style.display = "none";
                return;
            }

            // Есть запрос — показать плоские результаты
            searchResults.style.display = "";
            instituteList.style.display = "none";

            var visible = 0;
            searchItems.forEach(function (card) {
                var name = normalize(card.textContent);
                var match = name.indexOf(query) !== -1;
                card.classList.toggle("hidden", !match);
                if (match) visible++;
            });

            noResults.style.display = visible === 0 ? "" : "none";
        });
    }

    // Поиск на странице преподавателей (без иерархии)
    var groupCards = document.querySelectorAll(".group-list:not(.search-results) .group-card");
    if (searchBox && !searchItems.length && groupCards.length) {
        searchBox.addEventListener("input", function () {
            var query = normalize(this.value);
            var visible = 0;

            groupCards.forEach(function (card) {
                var name = normalize(card.textContent);
                var match = !query || name.indexOf(query) !== -1;
                card.classList.toggle("hidden", !match);
                if (match) visible++;
            });

            if (noResults) {
                noResults.style.display = (query && visible === 0) ? "" : "none";
            }
        });
    }
});
