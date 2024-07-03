# Paper Patrol
This repository is a rewrite of [arxiv\_on\_deck](https://mfouesneau.github.io/arxiv_on_deck_2/).

The code goes through the new specific author lists and compiles a 1 page summary with figures.

This also contains scripts to compile the 'automated' Wordpress blogposts for isimba.dk


## Quick Start

```
Usage: main.py [options]

Options:
  -h, --help            Show this help message and exit
  -m HL_AUTHORS, --coworker=HL_AUTHORS
                        List of authors to highlight (co-workers)
  -i IDENTIFIER, --id=IDENTIFIER
                        Make postage of a single paper given by its arxiv id
  -a HL_AUTHORS, --authors=HL_AUTHORS
                        Highlight specific authors
```

## Quick set-up
Clone the repository. You need to edit the following files:
* `workplaces/{your_workplace}`: In this directory, you need to make a folder named after the institute you want to check for. This `idstr` be `bham`, `mpia`, `sac` or something along those lines.
* `workplaces/{your_workplace}/coworker.txt`: In this file you need to add the surnames of the coworkers you want to query for.
* `institutes.py`: In the class, you need to set up your workplace. I have left my institutes in there for inspiration. In `get_institute_dir`, you need to specify the `idstr` used as the name for the `workplaces` directory. In `get_institute_words` specify the keywords that need to be present in a `.tex` file from arXiv. See the file for inspiration.
* `dailyarxiv.py`: This is where everything is called. You need to create an `if` case for your workplace and change `place` so it runs your workplace as default.

## What is different from the Arxiver?
If you don't know the ArXiver, check it there: http://arxiver.moonhats.com/

The main difference comes from the additional content and output format.

Here is an overview of the steps the code does:
1. Get the list of new articles on arXiv.
2. Retrieve the information on each article including title, abstract, subjects.
3. Filter out all but selected authors (e.g., institute or group members)
4. Download the source, hunt for information in the paper source: figures, caption and labels
5. Generates a tex file with internal template with abstract, authors figures
   and captions. (takes care of compiling references from the original document)
6. Compile the document into pdf (figures are converted on the fly if necessary)


The figure selection remains simple in this version. It parses for the Arxiver
tag:
`%@arxiver{fig1.pdf,fig4.png,fig15.eps}`
or selects the most references figures throughout the text.


## Contributors
* Amalie Stokholm (@amaliestokholm)
* Mathias Rav (@mortable)

For the original `arxiv_on_deck`:
* Morgan Fouesneau (@mfouesneau)
* Iskren Y. Georviev (@iskren-y-g)
