document.addEventListener("DOMContentLoaded", function () {
    // Telegram WebApp SDK
    if (window.Telegram && Telegram.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
    }

    // === Избранное (localStorage) ===

    function getFavorites(key) {
        try {
            return JSON.parse(localStorage.getItem(key)) || [];
        } catch (e) {
            return [];
        }
    }

    function saveFavorites(key, list) {
        localStorage.setItem(key, JSON.stringify(list));
    }

    function isFavorite(key, name) {
        return getFavorites(key).indexOf(name) !== -1;
    }

    function toggleFavorite(key, name) {
        var favs = getFavorites(key);
        var idx = favs.indexOf(name);
        if (idx !== -1) {
            favs.splice(idx, 1);
        } else {
            favs.unshift(name);
        }
        saveFavorites(key, favs);
        return idx === -1; // true = добавлено
    }

    // Кнопка-звёздочка на странице расписания
    var favBtn = document.querySelector(".fav-btn");
    if (favBtn) {
        var type = favBtn.dataset.type;
        var name = favBtn.dataset.name;
        if (isFavorite(type, name)) {
            favBtn.classList.add("active");
        }
        favBtn.addEventListener("click", function () {
            var added = toggleFavorite(type, name);
            this.classList.toggle("active", added);
        });
    }

    // Секция избранного на страницах выбора
    var favSection = document.querySelector(".favorites-section");
    if (favSection) {
        var favType = favSection.dataset.type;
        var urlTemplate = favSection.dataset.urlTemplate;
        var favs = getFavorites(favType);
        if (favs.length > 0) {
            var html = '<div class="favorites-title">Избранное</div><div class="favorites-list">';
            favs.forEach(function (name) {
                var url = urlTemplate.replace("{name}", encodeURIComponent(name));
                html += '<a href="' + url + '" class="group-card fav-card">' + name + '</a>';
            });
            html += '</div>';
            favSection.innerHTML = html;
        }
    }

    // === Переключение табов (чёт/нечёт) ===

    var tabs = document.querySelectorAll(".tab");
    var weekContents = document.querySelectorAll(".week-content");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            var target = this.dataset.week;

            tabs.forEach(function (t) { t.classList.remove("active"); });
            this.classList.add("active");

            weekContents.forEach(function (wc) {
                wc.classList.toggle("active", wc.dataset.week === target);
            });
        });
    });

    // === Аккордеон: раскрытие/сворачивание дней ===

    document.querySelectorAll(".day-header").forEach(function (header) {
        header.addEventListener("click", function () {
            this.parentElement.classList.toggle("open");
        });
    });

    // === Поиск ===

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
                searchResults.style.display = "none";
                instituteList.style.display = "";
                if (favSection) favSection.style.display = "";
                noResults.style.display = "none";
                return;
            }

            searchResults.style.display = "";
            instituteList.style.display = "none";
            if (favSection) favSection.style.display = "none";

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

            if (favSection) {
                favSection.style.display = query ? "none" : "";
            }

            if (noResults) {
                noResults.style.display = (query && visible === 0) ? "" : "none";
            }
        });
    }
});
