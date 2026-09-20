# CCVis Administrator Manual

## Previous and Current Versions

- `/`: the starting page
- `/dfg/admin`: set up an experiment with a directly-follows graph
- `/admin`: set up an experiment with multiple tasks and idioms

## Starting Point for Creating a CCVis Experiment: `/admin`

### Navigation Bar

Click **Home** while setting up an experiment to save your progress as a draft. **Experiment Setup** can be used to set up an experiment without using the Experiments card.

### Datasets Card

You can upload a dataset, which consists of a log and a guideline, by clicking **Upload**, or delete the selected dataset by clicking **Manage**. Follow the instructions in the pop-up window and upload the files in the correct format.

### Experiments Card

You can set up an experiment by clicking either **Create New** or **Experiment Setup** in the navigation bar. You can delete selected experiments by clicking **Manage**. When you delete an experiment, all graphs, configurations, and data generated through participant interactions are also deleted.

Experiments can have three states: draft, published, and finished. Click **Continue Editing** to continue setting up an experiment, **Download Data** to retrieve interim or final results, or **Idioms** to download the graphs generated for the experiment. Only one experiment can be in the published state at a time. Hover over the **i** icon to see which tasks and idioms were selected for an experiment.

## Basic Information for a New Experiment: `/admin/experiments/new`

Choose a dataset as the basis for generating idioms, or upload your own task-and-idiom combinations. If you upload your own task-and-idiom combinations as a ZIP file, you will go directly to `/admin/experiments/overview`.

Returning to this page for an experiment created from a ZIP file shows which ZIP file is in use, including its filename, task count, and upload time, with links to view it on the Overview page or download it again. From here, you can replace it with a different ZIP file or discard it and switch to the dataset route. Both options preserve the experiment name and study design. Discarding the ZIP file cannot be undone, so download a copy first if you may need it later.

The program does not currently support generating idioms with multiple datasets, but the endpoint is available for future development.

## Pre-Questionnaire: `/admin/experiments/prequestionnaire`

Select the questions to include about the participant's demographics and background. This section can be left blank.

## Knowledge Questions: `/admin/experiments/knowledge`

Select questions to test the participant's expertise. This section can be left blank. Custom questions added by clicking **Add Question** in the Custom Questions card are saved in the database and are therefore also available for other experiments.

## Introductory Pages: `/admin/experiments/concepts`

Select the modules to include on the introductory pages to familiarize the participant with basic conformance-checking concepts in the Key Concept card and with the background of the particular dataset and experiment in the Before You Begin card. This section can be left blank.

## Task Selection: `/admin/experiments/task`

You can filter tasks by goal, means, or characteristics, or select them directly. Click the pen icon to edit a task's label and description; these changes apply only to the current experiment. You can also click **Add Task** to configure a custom task, which will not appear in other experiments.

## Idiom Selection: `/admin/experiments/idiom`

Click the eye button to see a preview generated using the default dataset and parameters. Click **Upload Custom Idiom** to upload a custom idiom for the selected task under a name of your choice. Custom tasks can only use custom idioms.

## Idiom Generation: `/admin/experiments/specify`

You will not go through this page if you selected only custom idioms on `/admin/experiments/idiom`. Follow the instructions when selecting parameters. Click **Generate Visualizations** to generate idioms according to the selected parameters. Tasks 13, 15, 16, 20, 30, and 33 allow you to select log-level attributes, which is another endpoint available for future multi-dataset support.

## Answer Format: `/admin/experiments/answer-format`

Determine the answer format and its content, such as options for single- or multiple-choice questions and axes for a matrix, by following the instructions.

## Overview and Adjustment: `/admin/experiments/overview`

You will go directly to this page if you uploaded a ZIP file on `/admin/experiments/new`. You can review and adjust the experiment settings on this page, and then publish the experiment or save it as a draft. All generated idioms can be downloaded as a ZIP file to reproduce an experiment. You will be notified if another experiment has already been published.

### Navigating Between Experiment Setup Steps

You can jump to any step in the setup process using the step bar below the navigation bar, or use **Previous Step** and **Next**. Everything is preserved when you move between pages, except that graphs generated on `/admin/experiments/specify` are not preserved when you click **Previous Step**.

## Pilot Study

We also conducted a pilot study. Its dataset and data analysis are available in the [Google Drive folder](https://drive.google.com/drive/folders/1OypWF65R078wO5-h0CZYOHoYONGaSr1R?usp=sharing).
