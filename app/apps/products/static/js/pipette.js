document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".pipette-image").forEach(img => {
        img.addEventListener("click", function (e) {
            const variantId = this.dataset.variantId;

            // рисуем картинку на canvas
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            canvas.width = this.width;
            canvas.height = this.height;
            ctx.drawImage(this, 0, 0, canvas.width, canvas.height);

            // координаты клика
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const pixel = ctx.getImageData(x, y, 1, 1).data;
            const [r, g, b] = pixel;

            // console.log("RGB:", r, g, b);

            // запрос на Django
            fetch(`/admin/products/productvariant/detect-color/?r=${r}&g=${g}&b=${b}&variant=${variantId}`)
                .then(res => res.json())
                .then(data => {
                    if (data.color) {
                        alert(`Определён цвет: ${data.color}`);
                        // ищем input у текущей строки и вставляем
                        const row = this.closest("tr");
                        if (row) {
                            const colorInput = row.querySelector("input[name$='color']");
                            if (colorInput) {
                                colorInput.value = data.color;
                            }
                        }
                    } else {
                        alert("Ошибка: " + data.error);
                    }
                });
        });
    });
});
