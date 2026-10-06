from decimal import Decimal
from gettext import translation
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import APIView, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser,AllowAny
from django.shortcuts import get_object_or_404
from .models import ProductBarcode, Supplier, Warehouse, StockMovement, InventoryDocument
from .serializers import (
    SupplierSerializer,
    WarehouseSerializer,
    StockMovementListSerializer,
    StockMovementCreateSerializer,
    InventoryDocumentSerializer
)
from django.db.models import Sum  # 🔥 ИСПРАВЛЕНО: Импортируем Sum для корректной работы сканера
from app.apps.products.models import Product, ProductVariant
from .permissions import IsSellerWarehouseOwner, IsSellerOrAdminReadOnly
from .services import process_inventory_document,  transfer_between_warehouses,return_to_supplier, inventory_adjustment
from .pdf import generate_invoice_pdf
from .inventory.barcode_scanner import scan_barcode

from django.shortcuts import render
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser # 🔥 Импортируем парсеры

# инеграция пасеа и сканера 

class ScannerFindByBarcodeOrSkuAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        query = request.data.get("query")
        if not query:
            return Response({"error": "Параметр query обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        query_clean = str(query).strip().lower()
        from app.apps.warehouse.models import ProductBarcode, Warehouse, StockMovement
        from app.apps.products.models import ProductVariant
        from app.apps.products.serializers import ProductVariantSerializer

        variant = ProductBarcode.objects.filter(code=query_clean).select_related('variant').first()
        variant = variant.variant if variant else ProductVariant.objects.filter(barcode=query).first()
        if not variant:
            variant = ProductVariant.objects.filter(code__iexact=query_clean).first()

        if variant:
            serializer = ProductVariantSerializer(variant)
            response_data = serializer.data
            response_data["status"] = "found"
            
            warehouse_obj = Warehouse.objects.filter(seller=request.user.seller_profile).first()
            if warehouse_obj:
                inc_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="in").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                out_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="out").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                response_data["stock_current"] = float(inc_current - out_current)
            else:
                response_data["stock_current"] = 0.0

            response_data["stock_total"] = float(variant.stock)
            response_data["variant_id"] = variant.id
            response_data["name"] = variant.variant_name or "Без названия"
            response_data["sku"] = variant.code
            response_data["barcode"] = variant.barcode
            return Response(response_data, status=status.HTTP_200_OK)
        
        return Response({"status": "not_found", "message": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)


class ScannerCreateAndAddAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        barcode = request.data.get("barcode")
        name = request.data.get("variant_name") or request.data.get("name")
        sku = request.data.get("sku", "")
        price = request.data.get("price", 0)
        cost_price = request.data.get("cost_price", 0)
        product_id = request.data.get("product")
        photo_file = request.FILES.get("photo")

        if not barcode and sku:
            barcode = sku

        if not barcode or not name:
            return Response({"error": "Поля barcode и name обязательны"}, status=status.HTTP_400_BAD_REQUEST)

        from app.apps.products.models import Product, ProductVariant
        from app.apps.warehouse.models import ProductBarcode

        if product_id and str(product_id).isdigit():
            product = Product.objects.filter(id=int(product_id)).first()
        else:
            product = Product.objects.create(name=name, seller=request.user.seller_profile)

        variant = ProductVariant.objects.create(
            product=product,
            variant_name=name,
            code=sku,
            price=Decimal(str(price or 0)),
            cost_price=Decimal(str(cost_price or 0)),
            barcode=barcode
        )
        
        if photo_file:
            variant.image = photo_file
            variant.save()

        ProductBarcode.objects.get_or_create(variant=variant, code=str(barcode).strip())

        from app.apps.products.serializers import ProductVariantSerializer
        serializer = ProductVariantSerializer(variant)
        response_data = dict(serializer.data)
        response_data["status"] = "found"
        response_data["variant_id"] = variant.id
        response_data["name"] = variant.variant_name
        response_data["sku"] = variant.code
        response_data["barcode"] = variant.barcode

        return Response(response_data, status=status.HTTP_201_CREATED)


class CreateVariantFromScannerAPIView(APIView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        data = request.data
        
        sku_value = str(data.get('code', '')).strip()  # Это sku/артикул из формы
        barcode_value = str(data.get('barcode', '')).strip()
        
        # 🔥 Логика: если штрихкода нет, но есть артикул, используем его как временный штрихкод
        if not barcode_value and sku_value:
            barcode_value = sku_value
            
        if not barcode_value:
            return Response({"error": "Необходимо указать штрихкод или артикул (SKU)"}, status=status.HTTP_400_BAD_REQUEST)

        product_id = data.get('product')
        variant_name = data.get('variant_name')
        price = data.get('price')
        cost_price = data.get('cost_price')

        if product_id:
            product = Product.objects.get(id=product_id)
        else:
            product = Product.objects.create(
                name=variant_name or f"Товар {barcode_value}",
                seller=request.user.seller_profile
            )

        price_decimal = Decimal(str(price)) if price else Decimal('0.00')
        cost_decimal = Decimal(str(cost_price)) if cost_price else Decimal('0.0000')

        variant = ProductVariant.objects.create(
            product=product,
            variant_name=variant_name or product.name,
            code=sku_value,
            price=price_decimal,         
            cost_price=cost_decimal,     
            barcode=barcode_value        # Пишем штрихкод/sku в основную карточку
        )

        # 🔥 Регистрируем штрихкод в справочнике сканера
        ProductBarcode.objects.get_or_create(variant=variant, code=barcode_value)

        return Response({
            "status": "success",
            "id": variant.id,
            "variant_name": variant.variant_name,
            "code": variant.code,
            "barcode": barcode_value
        }, status=status.HTTP_201_CREATED)

# нужно теперь залить в бд  из документов товары  и в них есть  sku  и  другие коды и эти коды надо  использовать  для генерации  штрихкода или qrcode  а только потом генерируеца свой штрих код и или код 


def scanner_mock_view(request):
    """Временная страница для тестирования физического сканера штрихкодов"""
    return render(request, 'warehouse/scanner_mock.html')




class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.filter(is_active=True)
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsSellerOrAdminReadOnly]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Supplier.objects.all()
        return Supplier.objects.filter(is_active=True)


class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, IsSellerWarehouseOwner]


    
    # Здесь добавляем/заменяем get_queryset
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Warehouse.objects.all()
        
        seller_profile = getattr(user, 'seller_profile', None)
        if seller_profile and seller_profile.is_active:
            return Warehouse.objects.filter(seller=seller_profile)
        return Warehouse.objects.none()


            
    def perform_create(self, serializer):
        seller_profile = getattr(self.request.user, 'seller_profile', None)
        if not seller_profile or not seller_profile.is_active:
            raise PermissionError("Ваш аккаунт заблокирован для создания склада")
        serializer.save(seller=seller_profile)


class StockMovementViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated, IsSellerWarehouseOwner]
    permission_classes = [AllowAny]


    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return StockMovementListSerializer
        return StockMovementCreateSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return StockMovement.objects.all()
        if hasattr(self.request.user, 'seller_profile'):
            return StockMovement.objects.filter(seller=self.request.user.seller_profile)
        return StockMovement.objects.none()
    
    
    @action(detail=False, methods=['post'], url_path='find_by_barcode_or_sku')
    def find_by_barcode_or_sku(self, request):
        """
        Общий эндпоинт для проверки товара на складе (вне документов).
        Ищет по штрихкоду или артикулу (SKU).
        """
        query = request.data.get("query")  # Сюда фронтенд передает считанную строку

        if not query:
            return Response(
                {"error": "Параметр query (штрихкод или SKU) обязателен"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        query_clean = str(query).strip().lower()
        
        # Подключаем модели
        from app.apps.warehouse.models import ProductBarcode
        from app.apps.products.models import ProductVariant
        # Импортируем твой сериализатор вариантов
        from app.apps.products.serializers import ProductVariantSerializer

        variant = None

        # 1. Сначала ищем по точному совпадению штрихкода в доп. таблице
        barcode_obj = ProductBarcode.objects.filter(code=query_clean).select_related('variant').first()
        if barcode_obj:
            variant = barcode_obj.variant

        # 2. Если не нашли, ищем по штрихкоду в основной модели товара
        if not variant:
            variant = ProductVariant.objects.filter(barcode=query).first()

        # 3. Если снова не нашли, проверяем поле артикула (code/sku)
        if not variant:
            variant = ProductVariant.objects.filter(code__iexact=query_clean).first()
            
        mode = request.data.get("mode", "customer")
        
        # --- ИТОГ ПОИСКА ---
        if variant:
            # Пропускаем объект через сериализатор, чтобы собрать все поля (включая product_name)
            serializer = ProductVariantSerializer(variant)
            
            # Делаем копию данных из сериализатора и добавляем техническое поле для фронтенда
            response_data = serializer.data
            response_data["status"] = "found"
            # Считаем остатки динамически по истории StockMovement
            from django.db.models import Sum
            from app.apps.warehouse.models import Warehouse, StockMovement

            # 1. Получаем склад из запроса. Если фронт его не прислал — берём самый первый активный склад селлера
            warehouse_id = request.data.get("warehouse")
            if warehouse_id:
                warehouse_obj = Warehouse.objects.filter(id=warehouse_id).first()
            else:
                warehouse_obj = Warehouse.objects.filter(seller=request.user.seller_profile).first()
            # 2. Считаем остаток на этом складе
            if warehouse_obj:
                inc_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="in").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                out_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="out").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                response_data["stock_current"] = float(inc_current - out_current)
            else:
                response_data["stock_current"] = 0.0
            # Заглушка под картинку, если у тебя поле называется по-другому (например, variant.image.url)
            response_data["image"] = variant.image.url if hasattr(variant, 'image') and variant.image else None
            # 1. Остаток на ТЕКУЩЕМ складе (где сейчас происходит действие)
            # Приходы на этот склад
            inc_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="in").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            # Расходы с этого склада
            out_current = StockMovement.objects.filter(variant=variant, warehouse=warehouse_obj, movement_type="out").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            response_data["stock_current"] = float(inc_current - out_current)
            # 2. Общий остаток по всей сети (берём готовый кэш из карточки, это быстро)
            response_data["stock_total"] = float(variant.stock)
            
            # 3. Подтягиваем информацию о последней поставке для Хозяина
            last_in = StockMovement.objects.filter(variant=variant, movement_type="in").select_related('supplier', 'inventory_document').last()
            if last_in:
                response_data["last_supplier"] = last_in.supplier.name if last_in.supplier else "Неизвестный поставщик"
                response_data["last_delivery_date"] = last_in.created_at.strftime("%d.%m.%Y")
                response_data["last_document_number"] = last_in.document_number or "—"
            else:
                response_data["last_supplier"] = None
                
                
            
            # Дополнительный фикс на случай, если фронтенд старой версии ищет именно t.variant_id или t.name
            response_data["variant_id"] = variant.id
            response_data["name"] = variant.variant_name or (variant.product.name if variant.product else "Без названия")
            response_data["sku"] = variant.code  # Сопоставляем code с ожидаемым на фронте sku
            response_data["barcode"] = variant.barcode
            
            if mode == "customer":
                # Защита данных: удаляем технические поля для покупательского экрана
                response_data.pop("cost_price", None) # убираем себестоимость
                response_data.pop("variant_id", None)
                response_data.pop("stock_current", None)
                response_data.pop("stock_total", None)

            return Response(response_data, status=status.HTTP_200_OK)
        
        else:
            # Товар не найден вообще в системе. 
            return Response({
                "status": "not_found",
                "query": query,
                "message": "Данный штрихкод или артикул не зарегистрирован в системе."
            }, status=status.HTTP_404_NOT_FOUND)
    

    
    @action(detail=False, methods=['post'], url_path='create_and_add', parser_classes=[MultiPartParser, FormParser, JSONParser])
    def create_and_add(self, request):
        """
        API для быстрого создания абсолютно нового товара прямо со сканера
        и мгновенного добавления его в накладную (CRUD: Create).
        """
        barcode = request.data.get("barcode")
        # name = request.data.get("name")
        name = request.data.get("variant_name") or request.data.get("name")
        sku = request.data.get("sku", "")
        document_id = request.data.get("document")
        warehouse_id = request.data.get("warehouse")
        price = request.data.get("price", 0)
        quantity = request.data.get("quantity", 1)
        cost_price = request.data.get("cost_price", 0) # 🔥 Добавили закупку
        product_id = request.data.get("product")
        photo_file = request.FILES.get("photo")
        photo_url = request.data.get("photo_url")
        # Подстраховка по кодам
        if not barcode and sku:
            barcode = sku

        if not barcode or not name:
            return Response(
                {"error": "Поля barcode, name, document и warehouse обязательны"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
            
            
            # 🔥 ВЫВОДИМ В ТЕРМИНАЛ ТО, ЧТО ПРИШЛО С ФРОНТЕНДА ДЛЯ ПРОВЕРКИ
        print(f"=== ДЕБАГ СКАНЕРА ===")
        print(f"ID Документа (document): {document_id}")
        print(f"ID Склада (warehouse): {warehouse_id}")
        print(f"Текущий пользователь: {request.user} (Seller Profile ID: {getattr(request.user, 'seller_profile', None)})")
        print(f"=====================")

        document = get_object_or_404(InventoryDocument, id=document_id, seller=request.user.seller_profile)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id, seller=request.user.seller_profile)
        
        
        
        if not document:
            print(f"❌ ОШИБКА: Документ с ID {document_id} не найден в базе или не принадлежит этому селлеру!")
            return Response({"error": f"Документ с ID {document_id} не найден или доступ запрещен"}, status=status.HTTP_404_NOT_FOUND)

        if not warehouse:
            print(f"❌ ОШИБКА: Склад с ID {warehouse_id} не найден в базе или не принадлежит этому селлеру!")
            return Response({"error": f"Склад с ID {warehouse_id} не найден или доступ запрещен"}, status=status.HTTP_404_NOT_FOUND)

        from app.apps.products.models import Product, ProductVariant
        from app.apps.warehouse.models import ProductBarcode
        from decimal import Decimal

        # 1. Создаем продукт и вариант в базе
        # product = Product.objects.create(name=name, seller=request.user.seller_profile)
        # Если родительский продукт не выбран, создаем новый базовый продукт автоматичеки
        if product_id and product_id.isdigit():
            product = Product.objects.get(id=int(product_id))
        else:
            product = Product.objects.create(name=name, seller=request.user.seller_profile)
        variant = ProductVariant.objects.create(
            product=product,
            variant_name=name,
            code=sku,
            price=Decimal(str(price)),
            cost_price=Decimal(str(cost_price)), # 🔥 Пишем закупку в 4 знака
            barcode=barcode
        )
        
        # Если загрузили файл напрямую (с телефона/ПК) — сохраняем
        if photo_file:
            variant.image = photo_file  # или то имя поля, которое у тебя в ProductVariant под ImageField
            variant.save()
        # Если прислали просто URL-ссылку на изображение
        elif photo_url:
            variant.photo_url = photo_url # или пиши в кастомное текстовое поле
            variant.save()

        # 2. Регистрируем штрихкод в справочнике сканера
        ProductBarcode.objects.get_or_create(variant=variant, code=str(barcode).strip())

        # 3. Сразу делаем движение прихода в документ, чтобы кладовщику не надо было пикать заново
        movement = StockMovement.objects.create(
            inventory_document=document,
            variant=variant,
            seller=request.user.seller_profile,
            warehouse=warehouse,
            movement_type="in",
            quantity=Decimal(str(quantity)), # Наш новый Decimal
            # quantity=int(quantity),
            supplier=document.supplier,
            document_number=document.document_number,
            # price_per_unit=Decimal(str(price)),
            price_per_unit=Decimal(str(cost_price)), # В движение пишется ЗАКУПКА
            created_by=request.user,
            comment=f"Добавлено вручную со сканера (Новый товар)"
        )
        
        # Возвращаем объект в том же формате сериализатора, чтобы фронт сразу его отрендерил
        from app.apps.products.serializers import ProductVariantSerializer
        serializer = ProductVariantSerializer(variant)
        response_data = dict(serializer.data)
        response_data["status"] = "found"

        # return Response({
        #     "status": "created",
        #     "variant_id": variant.id,
        #     "name": variant.variant_name,
        #     "current_doc_qty": movement.quantity,
        #     "message": "Новый товар успешно зарегистрирован и добавлен в документ!"
        # }, status=status.HTTP_201_CREATED)
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Краткая сводка по движениям (можно расширить)"""
        qs = self.get_queryset()
        data = {
            'total_in': qs.filter(movement_type='in').count(),
            'total_out': qs.filter(movement_type='out').count(),
            'last_movement': qs.first().created_at if qs.exists() else None
        }
        return Response(data)
    
    


    @action(detail=False, methods=['post'])
    def transfer(self, request):
        """API перемещения между складами"""
        variant_id = request.data.get("variant")
        from_wh_id = request.data.get("from_warehouse")
        to_wh_id = request.data.get("to_warehouse")
        qty = int(request.data.get("quantity", 0))

        # ИСПРАВЛЕНО: Безопасно получаем объекты, чтобы передать их в сервис
        variant = get_object_or_404(ProductVariant, id=variant_id)
        from_warehouse = get_object_or_404(Warehouse, id=from_wh_id, seller=request.user.seller_profile)
        to_warehouse = get_object_or_404(Warehouse, id=to_wh_id)
        # 1. Выполняем само перемещение (оно создаст StockMovement)
        transfer_between_warehouses(
            variant=variant,
            from_warehouse=from_warehouse,
            to_warehouse=to_warehouse,
            quantity=qty,
            user=request.user
        )
        
        # # 2. 🔥 СРАЗУ ОБНОВЛЯЕМ КЭШ ОСТАТКА check signal;s 
        # from .services import recalculate_variant_stock
        # recalculate_variant_stock(variant)
        
        return Response({"status": "transferred"}, status=status.HTTP_200_OK)
    

    
    @action(detail=False, methods=['post'])
    def return_supplier(self, request):
        """API возврата поставщику"""
        variant_id = request.data.get("variant")
        warehouse_id = request.data.get("warehouse")
        supplier_id = request.data.get("supplier")
        qty = int(request.data.get("quantity", 0))

        # ИСПРАВЛЕНО: Превращаем ID в полноценные объекты базы данных
        variant = get_object_or_404(ProductVariant, id=variant_id)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id, seller=request.user.seller_profile)
        supplier = get_object_or_404(Supplier, id=supplier_id)

        return_to_supplier(
            variant=variant,
            warehouse=warehouse,
            supplier=supplier,
            quantity=qty,
            user=request.user
        )
        
        # from .services import recalculate_variant_stock check signasl
        # recalculate_variant_stock(variant)
        
        return Response({"status": "returned"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def inventory(self, request):
        """API инвентаризации"""
        variant_id = request.data.get("variant")
        warehouse_id = request.data.get("warehouse")
        real_qty = int(request.data.get("quantity", 0))

        # ИСПРАВЛЕНО: Находим объекты перед вызовом сервиса корректировки остатков
        variant = get_object_or_404(ProductVariant, id=variant_id)
        warehouse = get_object_or_404(Warehouse, id=warehouse_id, seller=request.user.seller_profile)

        inventory_adjustment(
            variant=variant,
            warehouse=warehouse,
            real_quantity=real_qty,
            user=request.user
        )
        
        # # 🔥 Обновляем кэш! signal must work
        # from .services import recalculate_variant_stock
        # recalculate_variant_stock(variant)
        
        
        return Response({"status": "inventory done"}, status=status.HTTP_200_OK)
    



class InventoryDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryDocumentSerializer
    permission_classes = [IsAuthenticated, IsSellerWarehouseOwner]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return InventoryDocument.objects.all()
        if hasattr(self.request.user, 'seller_profile'):
            return InventoryDocument.objects.filter(seller=self.request.user.seller_profile)
        return InventoryDocument.objects.none()

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user.seller_profile)
        
    @action(detail=True, methods=['get'])
    def print(self, request, pk=None):
        '''API печати'''
        document = self.get_object()

        path = generate_invoice_pdf(document)

        return Response({"pdf": path})
    
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Провести документ через НОВЫЙ автоматический парсер.
        Это единственная точка входа, заменяющая старый экшен 'accept'.
        """
        document = self.get_object()
        
        if document.processed:
            return Response({"error": "Документ уже был обработан ранее"}, status=status.HTTP_400_BAD_REQUEST)

        # Выбираем дефолтный склад продавца
        warehouse = Warehouse.objects.filter(seller=request.user.seller_profile, is_default=True).first() or \
                    Warehouse.objects.filter(seller=request.user.seller_profile).first()

        if not warehouse:
            return Response({"error": "У вашего профиля не найден зарегистрированный склад"}, status=status.HTTP_400_BAD_REQUEST)

        # Передаем управление сервису умного распознавания
        process_inventory_document(
            document=document,
            warehouse=warehouse,
            created_by=request.user
        )

        return Response({"status": "document processed"}, status=status.HTTP_200_OK)
        

    
    @action(detail=True, methods=['post'])
    def scan(self, request, pk=None):
        """
        Сканирование штрихкода в процессе приемки документа
        """
        document = self.get_object()
        barcode = request.data.get("barcode")
        warehouse_id = request.data.get("warehouse")

        if not barcode or not warehouse_id:
            return Response(
                {"error": "barcode and warehouse are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        warehouse = Warehouse.objects.filter(id=warehouse_id, seller=request.user.seller_profile).first()
        if not warehouse:
            return Response({"error": "Warehouse not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Вызываем наш обновленный сканнер
            from django.core.exceptions import ObjectDoesNotExist
            variant = scan_barcode(
                document=document,
                barcode=barcode,
                warehouse=warehouse,
                user=request.user
            )
            
            
            # Получаем текущее суммарное количество товара в этой накладной после пика
            total_qty_in_doc = StockMovement.objects.filter(
                inventory_document=document,
                variant=variant
            ).aggregate(total=Sum('quantity'))['total'] or 1

            return Response({
                "status": "success",
                "variant_id": variant.id,
                "name": variant.variant_name,
                "sku": variant.code,
                "current_doc_qty": total_qty_in_doc,
                "message": "Количество обновлено (+1)"
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist as e:
            # Перехватываем "Товар не найден" и отдаем 404 статус + сам считанный штрихкод
            return Response({
                "status": "not_found",
                "barcode": barcode,
                "message": "Такой товар еще не зарегистрирован в системе. Открыть форму создания?"
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        document = self.get_object()
        
        if document.processed:
            return Response({"error": "already processed"})

        # распознаем файл
        extract_document_data(document)

        # принимаем на склад
        warehouse = Warehouse.objects.filter(
            seller=request.user.seller_profile
        ).first()

        process_inventory_document(
            document=document,
            warehouse=warehouse,
            created_by=request.user
        )

        document.processed = True
        document.save()

        return Response({"status": "accepted"})