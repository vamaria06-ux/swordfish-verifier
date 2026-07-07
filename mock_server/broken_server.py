"""
Mock-сервер с намеренными ошибками для тестирования верификатора.
Запуск: python mock_server/broken_server.py
Сервер запустится на http://localhost:5001
"""

from flask import Flask, jsonify

app = Flask(__name__)

# Идентификатор "системы", под которой эмулируются динамические ресурсы
# StoragePools/Volumes/Drives (см. verifier/parser.py: RESOURCE_ENDPOINTS,
# main.py: get_system_urls/run_checks). main.py подставляет сюда
# @odata.id из Members коллекции /redfish/v1/Systems (см. ниже).
SYSTEM_ID = "1"
SYSTEM_URL = f"/redfish/v1/StorageSystems/{SYSTEM_ID}"


@app.route("/redfish/v1/")
def service_root():
    """
    Намеренные ошибки:
    - нет поля @odata.type
    - нет поля Name
    - Id это число а не строка
    """
    return jsonify({
        "@odata.id": "/redfish/v1/",
        "Id": 123,           # должна быть строка
        "RedfishVersion": "1.0.0"
        # намеренно убрали @odata.type и Name
    }), 200


@app.route("/redfish/v1/StorageSystems")
def storage_systems():
    """
    Намеренные ошибки:
    - статус 404 вместо 200
    """
    return jsonify({
        "error": "Not found"
    }), 404


@app.route("/redfish/v1/StorageServices")
def storage_services():
    """
    Намеренные ошибки:
    - нет поля Members
    - нет поля Members@odata.count
    """
    return jsonify({
        "@odata.type": "#StorageServiceCollection.StorageServiceCollection",
        "@odata.id": "/redfish/v1/StorageServices"
        # намеренно убрали Members и Members@odata.count
    }), 200


@app.route("/redfish/v1/Systems")
def systems():
    """
    Всё правильно (PASS). Содержит один элемент в Members, чтобы
    верификатор мог получить {system_url} и перейти к проверке
    динамических ресурсов ниже -- StorageSystems специально ломает
    статус (см. выше), поэтому main.py берёт id системы отсюда
    (см. get_system_urls в main.py).
    """
    return jsonify({
        "@odata.type": "#ComputerSystemCollection.ComputerSystemCollection",
        "@odata.id": "/redfish/v1/Systems",
        "Members": [
            {"@odata.id": SYSTEM_URL}
        ],
        "Members@odata.count": 1
    }), 200


@app.route(f"{SYSTEM_URL}/StoragePools")
def storage_pools():
    """
    Намеренная ошибка: Members@odata.count имеет неверный тип
    (строка вместо целого числа).
    """
    return jsonify({
        "@odata.type": "#StoragePoolCollection.StoragePoolCollection",
        "@odata.id": f"{SYSTEM_URL}/StoragePools",
        "Members": [],
        "Members@odata.count": "0"  # должно быть числом, а не строкой
    }), 200


@app.route(f"{SYSTEM_URL}/Volumes")
def volumes():
    """
    Намеренная ошибка: отсутствуют обязательные поля Members и
    Members@odata.count.
    """
    return jsonify({
        "@odata.type": "#VolumeCollection.VolumeCollection",
        "@odata.id": f"{SYSTEM_URL}/Volumes"
        # намеренно убрали Members и Members@odata.count
    }), 200


# {SYSTEM_URL}/Drives намеренно не реализован: демонстрирует
# отсутствующий эндпоинт (Flask вернёт свой стандартный 404 Not Found).


if __name__ == "__main__":
    print("\n=== Broken Mock Server ===")
    print("Запущен на http://localhost:5001")
    print("Намеренные ошибки:")
    print("  /redfish/v1/                     — нет @odata.type, нет Name, Id=число")
    print("  /redfish/v1/StorageSystems       — статус 404")
    print("  /redfish/v1/StorageServices      — нет Members")
    print("  /redfish/v1/Systems              — всё правильно (PASS), содержит 1 систему")
    print(f"  {SYSTEM_URL}/StoragePools — Members@odata.count неверного типа (строка)")
    print(f"  {SYSTEM_URL}/Volumes      — нет Members / Members@odata.count")
    print(f"  {SYSTEM_URL}/Drives       — эндпоинт отсутствует (404)\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
