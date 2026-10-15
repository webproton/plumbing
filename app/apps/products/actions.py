from django import forms
from django.shortcuts import render, redirect
import logging
from django.contrib import admin


from django import forms
from .models import *

logger = logging.getLogger(__name__)

from .models import *


class DiscountForm(forms.Form):
    discount = forms.IntegerField(label="Скидка (%)", required=True)

    def clean(self):
        cleaned_data = super().clean()
        logger.debug(f"Form cleaned_data: {cleaned_data}")
        discount = cleaned_data.get('discount')
        if discount is not None and (discount < 0 or discount > 100):
            raise forms.ValidationError("Скидка должна быть от 0 до 100%.")
        return cleaned_data

def apply_discount_to_variants(modeladmin, request, queryset):
    logger.debug("Action apply_discount_to_variants triggered")
    logger.debug(f"Selected variants: {[variant.pk for variant in queryset]}")


    if request.method  == "POST":
        logger.debug(f"POST request received: {request.POST}")
        form = DiscountForm(request.POST)
        if form.is_valid():
            discount_value = form.cleaned_data['discount']
            logger.debug(f"Applying discount: {discount_value}%")
            count = 0
            for variant in queryset:
                logger.debug(f"Processing variant ID: {variant.pk}")
                current_original = variant.original_price
                current_price = variant.price
                if discount_value > 0:
                    if current_original is None:
                        original_price = current_price
                    else:
                        original_price = current_original

                    variant.discount = discount_value
                    variant.original_price = original_price
                    variant.price = original_price * (Decimal('1') - Decimal(discount_value) / Decimal('100'))
                else:
                    variant.discount = 0
                    variant.price = current_original if current_original is not None else current_price
                    variant.original_price = None

                variant.save()
                count += 1
            modeladmin.message_user(request, f"Скидка {discount_value}% применена к {count} вариантам.")
            logger.debug(f"Discount applied to {count} variants")
            return redirect(request.get_full_path())
        else:
            logger.error(f"Form errors: {form.errors}")
    else:
        form = DiscountForm()
        logger.debug("Rendering form")

    return render(request, "admin/apply_discount.html", {
        'form': form,
        'products': queryset,

        "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,  # ✅ правильное имя чекбоксов
    })
