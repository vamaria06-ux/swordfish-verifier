"""
Mock-сервер с намеренными ошибками для тестирования верификатора.
Запуск: python mock_server/broken_server.py
Сервер запустится на http://localhost:5001
"""

from flask import Flask, jsonify

app = Flask(__name__)


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
    Правильный ответ — этот ресурс должен дать PASS
    чтобы показать что верификатор различает правильное и неправильное
    """
    return jsonify({
        "@odata.type": "#ComputerSystemCollection.ComputerSystemCollection",
        "@odata.id": "/redfish/v1/Systems",
        "Members": [],
        "Members@odata.count": 0
    }), 200


if __name__ == "__main__":
    print("\n=== Broken Mock Server ===")
    print("Запущен на http://localhost:5001")
    print("Намеренные ошибки:")
    print("  /redfish/v1/          — нет @odata.type, нет Name, Id=число")
    print("  /redfish/v1/StorageSystems  — статус 404")
    print("  /redfish/v1/StorageServices — нет Members")
    print("  /redfish/v1/Systems         — всё правильно (PASS)\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
