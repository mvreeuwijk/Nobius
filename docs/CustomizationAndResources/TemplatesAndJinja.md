# Templates and Jinja
This tool uses the python Jinja2 templating engine to generate html pages which make up questions. It uses Jinja macros as modular building blocks, and custom filters when more complex operations are required. For example, the root template `templates/manifests/assignment.xml` will make use of the `templates/questions/question_template.xml` macro which itself makes use of `templates/layouts/exercise.html`. These template files are contained in the `templates` folder.

For more information on how to use Jinja, it's [documentation](https://jinja.palletsprojects.com/en/2.11.x/templates/) is really good.
