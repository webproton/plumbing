"""SEO: данные для sitemap.xml, код Google Search Console и данные для Google Business Profile."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.tests.factories import CategoryFactory, ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db
TOKEN = "AbC-123_xyzTOKENvalue0987"


@pytest.fixture
def admin():
    client = APIClient()
    client.force_authenticate(UserFactory(is_superuser=True))
    return client


def test_sitemap_lists_only_visible_products_and_non_empty_categories():
    shown = CategoryFactory(name="Змішувачі")
    CategoryFactory(name="Дивани")  # пустая — поисковику не нужна
    visible = ProductFactory(name="Змішувач для кухні", category=shown, photo="products/mix.jpg")
    ProductVariantFactory(product=visible, available=True)
    hidden = ProductFactory(name="Скритий товар", category=CategoryFactory(name="Приховані"))
    ProductVariantFactory(product=hidden, available=False)

    data = APIClient().get(reverse("marketing:seo-sitemap")).json()
    assert [(p["slug"], p["image"]) for p in data["products"]] == [(visible.slug, "/media/products/mix.jpg")]
    assert [c["slug"] for c in data["categories"]] == [shown.slug]
    assert len(data["products"][0]["updated"]) == 10  # YYYY-MM-DD


def test_google_verification_code_taken_from_pasted_meta_tag(admin):
    url = reverse("callback:shop-settings")
    tag = f'<meta name="google-site-verification" content="{TOKEN}" />'
    resp = admin.patch(url, {"google_site_verification": tag}, format="json")
    assert resp.status_code == 200, resp.json()
    assert resp.json()["google_site_verification"] == TOKEN  # регистр сохранён

    bad = admin.patch(url, {"google_site_verification": '"><script>alert(1)</script>'}, format="json")
    assert bad.status_code == 400 and "google_site_verification" in bad.json()


def test_business_details_are_public(admin):
    admin.patch(
        reverse("callback:shop-settings"),
        {
            "phone": "+380441234567",
            "pickup_address": "Київ, вул. Сантехнічна, 5",
            "opening_hours": "Пн–Пт 9:00–18:00, Сб 10:00–15:00",
            "google_business_url": "https://maps.app.goo.gl/abc123",
            "google_site_verification": TOKEN,
        },
        format="json",
    )
    public = APIClient().get(reverse("callback:site-settings")).json()
    assert public["pickup_address"] == "Київ, вул. Сантехнічна, 5"
    assert public["opening_hours"].startswith("Пн–Пт")
    assert public["google_business_url"] == "https://maps.app.goo.gl/abc123"
    assert public["google_site_verification"] == TOKEN
