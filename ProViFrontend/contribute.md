# Contribute 






#### Questionnaire CSV Datei

Important to not use Excel due to format problems leads to breaking of questionnaire component
Recommended text editor: normal Text Editor like Notepad++

NOCH ANPASSEN:

const questionsCsv = `Question ID,Question Text,Answer Type,Options
1,"What activities do you think are redundant?",text,
2,"Which of the following activities should be optimized?",multiple choice,"Activity A|Activity B|Activity C"
3,"How would you rate the efficiency of the current process?",rating,
4,"Which activities do you find the most problematic?",multiple select,"Activity A|Activity B|Activity C|Activity D"
`;

question type: follow-up question: special case: base question if answer yes-> normal routing to subquestion (right after base question in csv)
                                                               if answer no -> skip next question (adds 2 to index)
example base: id:23, follow-up question: id:24