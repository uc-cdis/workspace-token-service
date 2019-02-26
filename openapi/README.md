# OpenAPI spec

The [OpenAPI](https://github.com/OAI/OpenAPI-Specification)/[Swagger 2.0](https://swagger.io/) specification of a service is stored in its `swagger.yaml` file. It can be visualized using the Swagger UI at `http://petstore.swagger.io/?url=<swagger.yaml raw URL>`. For example, the documentation found in this folder can be visualized [here](http://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/service-template/master/openapi/swagger.yaml).

# To generate the documentation

* update the docstring of the endpoints impacted by the changes;
* run `python build_openapi.py`;
* validate the updated `swagger.yaml` using the [Swagger editor](http://editor.swagger.io);
* git push `swagger.yaml`.
