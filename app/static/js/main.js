const grid = document.getElementById("restaurant-grid");
const searchInput = document.getElementById("search-input");
const navSearchInput = document.getElementById("nav-search");
const foodFilter = document.getElementById("food-filter");
const ratingFilter = document.getElementById("rating-filter");
const healthyFilter = document.getElementById("healthy-filter");
const radiusFilter = document.getElementById("radius-filter");
const locationBtn = document.getElementById("location-btn");
const locationStatus = document.getElementById("location-status");
const razorpayPayBtn = document.getElementById("razorpay-pay-btn");

let map;
let markerLayer;
let userCoords = null;
let lastRestaurants = [];

function syncSearchInputs(source, target) {
    if (!source || !target) return;
    if (target.value !== source.value) target.value = source.value;
}

function skeletonMarkup(count = 6) {
    return Array.from({ length: count })
        .map(() => '<article class="skeleton-card"></article>')
        .join("");
}

function renderRestaurantCard(restaurant) {
    const distanceLabel = restaurant.distance !== null ? `${restaurant.distance} km away` : `${restaurant.city}`;
    const tags = [
        restaurant.category === "diet" || restaurant.category === "veg" ? '<span class="tag">Healthy 🥗</span>' : "",
        restaurant.popular ? '<span class="tag">Popular 🔥</span>' : "",
        restaurant.distance !== null ? `<span class="tag">${restaurant.distance} km</span>` : "",
    ].join("");

    return `
        <article class="restaurant-card">
            <img loading="lazy" src="${restaurant.image_url}" alt="${restaurant.name}">
            <div class="restaurant-card-overlay">
                <div class="restaurant-topline">
                    <div>
                        <h3>${restaurant.name}</h3>
                        <p>${restaurant.area}, ${restaurant.city}</p>
                    </div>
                    <strong>⭐ ${restaurant.rating}</strong>
                </div>
                <div class="nutrition-row">${tags}</div>
                <p>${restaurant.cuisine}</p>
                <div class="menu-footer">
                    <span>${distanceLabel} • ${restaurant.delivery_time} mins</span>
                    <a href="/restaurants/${restaurant.id}" class="btn btn-mini">View Menu</a>
                </div>
            </div>
        </article>
    `;
}

async function loadRestaurants() {
    if (!grid) return;

    grid.innerHTML = skeletonMarkup();
    const params = new URLSearchParams({
        search: searchInput?.value || navSearchInput?.value || "",
        food_type: foodFilter?.value || "",
        rating: ratingFilter?.value || "0",
        healthy: healthyFilter?.checked ? "true" : "false",
        radius: radiusFilter?.value || "10",
    });

    if (userCoords) {
        params.set("lat", userCoords.latitude);
        params.set("lng", userCoords.longitude);
    }

    try {
        const response = await fetch(`/restaurants/data?${params.toString()}`);
        const restaurants = await response.json();
        lastRestaurants = restaurants;
        grid.innerHTML = restaurants.length
            ? restaurants.map(renderRestaurantCard).join("")
            : "<p>No nearby restaurants matched these filters. Try a wider radius.</p>";
        updateMap();
    } catch (_error) {
        grid.innerHTML = "<p>Unable to load restaurants right now.</p>";
    }
}

function initMap() {
    const mapNode = document.getElementById("map");
    if (!mapNode || map) return;

    map = L.map("map").setView([17.385, 78.4867], 7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
}

function updateMap() {
    if (!map || !markerLayer) return;

    markerLayer.clearLayers();
    lastRestaurants.forEach((restaurant) => {
        if (restaurant.lat == null || restaurant.lng == null) return;
        L.marker([restaurant.lat, restaurant.lng])
            .bindPopup(`<strong>${restaurant.name}</strong><br>${restaurant.area}, ${restaurant.city}`)
            .addTo(markerLayer);
    });

    if (userCoords) {
        L.circleMarker([userCoords.latitude, userCoords.longitude], {
            radius: 8,
            color: "#fc8019",
            fillColor: "#fc8019",
            fillOpacity: 1,
        }).bindPopup("You are here").addTo(markerLayer);
        map.setView([userCoords.latitude, userCoords.longitude], 11);
    }
}

function requestLocation() {
    if (!navigator.geolocation) {
        if (locationStatus) locationStatus.textContent = "Geolocation is not supported in this browser.";
        return;
    }

    if (locationStatus) locationStatus.textContent = "Finding restaurants near your live location...";

    navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
            userCoords = coords;
            if (locationStatus) {
                locationStatus.textContent = `Showing restaurants within ${radiusFilter?.value || 10} km of your live location.`;
            }
            loadRestaurants();
        },
        () => {
            if (locationStatus) locationStatus.textContent = "Location access denied. Showing Telangana-wide discovery feed.";
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

async function triggerRazorpayCheckout() {
    if (!window.foodSprintCheckout?.enabled) return;
    razorpayPayBtn.disabled = true;
    razorpayPayBtn.textContent = "Preparing payment...";

    try {
        const orderResponse = await fetch(window.foodSprintCheckout.createOrderUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });
        const orderData = await orderResponse.json();
        if (!orderData.ok) throw new Error(orderData.message || "Unable to create order.");

        const options = {
            key: orderData.key,
            amount: orderData.amount,
            currency: orderData.currency,
            name: orderData.name,
            description: orderData.description,
            order_id: orderData.razorpay_order_id,
            prefill: orderData.prefill,
            theme: { color: "#fc8019" },
            handler: async function (response) {
                const verifyResponse = await fetch(window.foodSprintCheckout.verifyUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        internal_order_id: orderData.internal_order_id,
                        razorpay_order_id: response.razorpay_order_id,
                        razorpay_payment_id: response.razorpay_payment_id,
                        razorpay_signature: response.razorpay_signature,
                    }),
                });
                const verifyData = await verifyResponse.json();
                if (verifyData.ok) {
                    window.location.href = verifyData.redirect_url;
                } else {
                    window.location.href = `${window.foodSprintCheckout.failureUrl}?order_id=${orderData.internal_order_id}`;
                }
            },
            modal: {
                ondismiss: function () {
                    window.location.href = `${window.foodSprintCheckout.failureUrl}?order_id=${orderData.internal_order_id}`;
                },
            },
        };

        const razorpay = new window.Razorpay(options);
        razorpay.open();
    } catch (_error) {
        window.location.href = window.foodSprintCheckout.failureUrl;
    } finally {
        razorpayPayBtn.disabled = false;
        razorpayPayBtn.textContent = "Pay with Razorpay";
    }
}

[searchInput, foodFilter, ratingFilter, healthyFilter, radiusFilter].forEach((node) => {
    node?.addEventListener("input", loadRestaurants);
    node?.addEventListener("change", loadRestaurants);
});

searchInput?.addEventListener("input", () => syncSearchInputs(searchInput, navSearchInput));
navSearchInput?.addEventListener("input", () => {
    syncSearchInputs(navSearchInput, searchInput);
    if (grid) loadRestaurants();
});

locationBtn?.addEventListener("click", requestLocation);
razorpayPayBtn?.addEventListener("click", triggerRazorpayCheckout);

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    if (grid) loadRestaurants();
});
