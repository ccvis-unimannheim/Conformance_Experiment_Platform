## ccvis manual for admin

### Previous and Present

/: the starting page

/dfg/admin: set up an experiment with direct follows graph

/admin: set up an experiment of multiple tasks and idioms

### Starting Point for Creating a ccvis Experiment: /admin

##### Navigation Bar

Click on *Home* whenever you're setting up an experiment and your progress would be saved as draft. *Experiment Setup* can be used to set up an experiment without using the Experiments card.

##### Card: Datasets

You can **upload a dataset** (which consists of a log and a guideline) with  *Upload*  or delete the dataset you select with *Manage*. Follow the instrutions on the pop-up window and upload the files in right format.

##### Card: Experiments

You can **set up an experiment** with either *Create New* or *Experiment Setup* (on the navigation bar), and you can delete selected experiments with *Manage*. When you delete an experiments, all the graphs, configurations, and the data generated along interaction with participants would be deleted. 

There're three states of experiments: draft, published and finished. You can click on *Continue Editing* to further set up an experiment, *Download Data* to fetch the periodical or final result of an experiment, and *idioms* to download the graphs generated for the experiment.Only 1 experiment can be at the status of published at any given time. Hover on the "i" icon to see which tasks and idioms you chose for an experiment. 

### Basic Info for a New Experiment: /admin/experiments/new

Choose a dataset to lay the foundation for generating idioms or upload your own task&idiom combinations. If you upload your own task&idiom combinations in a zip, you'll go directly to /admin/experiments/overview.

Returning to this page for a zip-built experiment shows which zip is in use (file, task count, upload time), with links to view it on Overview or re-download it. From here you can replace with a different zip, or Discard it and switch to the dataset route, both keep the name and study design. Discarding can't be undone, so download a copy first if you want it later.

Our program isn't currently supporting generating idioms with multiple datasets, but the endpoint is open for future development.

### Pre-Questionnaire: /admin/experiments/prequestionnaire

Select which questions to include about the participant's demographics and background. Can be left blank.

### Knowledge Question: /admin/experiments/knowledge

Select questions to test the participant's expertise. Can be left blank. Custom qustions you add with *Add Question* in Custom Questions card will be saved in the database, thus also available for other experiments.

### Introductory Pages: /admin/experiments/concepts

Select the modules you want to have on introductory pages to familiarize the participant with basic conformance checking concepts (Key Concept card) and background of this particular dataset and experiment (Before You Begin card).  Can be left blank.

### Task Selection: /admin/experiments/task

You can filter tasks by goal, means or characteristics or select right away. Click the pen icon to edit the task label and description, which would only persist in the current experiment. You can also use *Add Task* to configure your custom task, which also wouldn't show up in other experiments.

### Idiom  Selection: /admin/experiments/idiom

Click the eye button to see a preview generated from default dataset and parameters. Click *Upload Custom Idiom* to upload a custom idiom for the task you choose with the name you decide. Custom tasks only take custom idioms. 

### Idiom Generation: /admin/experiments/specify

You won't go through this page if you selected only custom idioms on /admin/experiments/idiom. Pay attention to the instrution when you're selecting the parameters. Click *Generate Visualizations* to generate the idioms according to the parameters you choose. It's worth noting that task13, task15, task16, task20, task30, and task33 allow you to choose attributes from log level, which is another endpoint left open for future multi-dataset support.

### Answer Format: /admin/experiments/answer-format

determine the answer format and the content (eg. options for single/multiple choices, axis for matrix) following the instructions.

### Overview and Adjustment: /admin/experiments/overview

You'll directly go to this page if you uploaded a zip on /admin/experiments/new. You can overview your settings for the experiment and adjust each of them on this page, and publish or save as draft. All idioms generated can be downloaded as a zip for reproduction of an experiment. You'll be notified if there's already an experiment published.

#### Special Note: navigating between experiment setup steps

You can jump to any step in the setting with the bar below navigation bar, or you can use *Previous Step* and *Next*. Everything would be preserved when jumping between pages, except for graphs generated when hitting *Previous Step* on /admin/experiments/specify.

##### We also did a pilot study，whose dataset and data analysis you can find here：https://drive.google.com/drive/folders/1OypWF65R078wO5-h0CZYOHoYONGaSr1R?usp=sharing




