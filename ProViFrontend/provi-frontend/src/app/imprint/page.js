import React from "react";
import Link from "next/link";
import Navigation from "../../components/General/Navigation";
const Imprint = () => {
  return (
    <div className="container p-8 mx-auto">
      <Navigation />

      <header className="mt-10 mb-8">
        <h1 className="mb-2 text-2xl font-bold text-center">About This Site</h1>
      </header>
      <div className="space-y-8">
        <section className="p-6 bg-white rounded-lg">
          <h2 className="mb-2 text-xl font-semibold">
            This website is published by
          </h2>
          <p>
            University of Mannheim
            <br /> Schloss
            <br /> 68161 Mannheim
            <br /> Tel. 0621/181-2222
          </p>
          <p>
            E-Mail:{" "}
            <a
              href="mailto:impressum@uni-mannheim.de"
              className="text-blue-500 hover:underline"
            >
              impressum@uni-mannheim.de
            </a>
            <br /> Internet:{" "}
            <a
              href="https://www.uni-mannheim.de"
              className="text-blue-500 hover:underline"
            >
              https://www.uni-mannheim.de
            </a>
          </p>
          <p>
            According to section 1 and section 8 subsection 1 of the act on the
            higher education institutions in the Land of Baden-Württemberg
            (Landeshochschulgesetz, LHG), the University of Mannheim is a body
            governed by public law. The university is represented by the
            President.
          </p>
          <p>
            VAT identification number (pursuant to Section 27a of the German
            Value Added Tax Act): DE 143845342
          </p>
        </section>

        <section className="p-6 bg-white rounded-lg">
          <h2 className="mb-2 text-xl font-semibold">
            Responsible in terms of content
          </h2>
          <p>
            The Marketing and Communications departments in the Presidents
            Office manage the contents of the central websites.
          </p>
          <p>
            The responsibility for journalistic and editorial contents lies
            with:
          </p>
          <p>Dr. Andreas Margara (Head of the Marketing Department)</p>
          <p>
            University of Mannheim
            <br /> Rectorate, Marketing Department
            <br /> Schloss Ostflügel
            <br /> 68161 Mannheim
          </p>
        </section>

        <section className="p-6 bg-white rounded-lg">
          <h2 className="mb-2 text-xl font-semibold">Copyright information</h2>
          <p>
            The texts, images, photographs, videos or graphics as well as the
            layout of our website are protected by copyright law. The webpages
            may be copied for private use only. Any other use (in particular the
            distribution of copies or changes to the content) is prohibited
            unless otherwise specified. If you intend to use the website or
            parts thereof, please contact us in advance via the details above.{" "}
          </p>
        </section>

        <section className="p-6 bg-white rounded-lg">
          <h2 className="mb-2 text-xl font-semibold">Social media profiles</h2>
          <ul className="list-disc list-inside">
            <li>
              <em>Instagram</em>:{" "}
              <a
                href="https://www.instagram.com/uni_mannheim/"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                instagram.com/uni_mannheim
              </a>
            </li>
            <li>
              <em>TikTok</em>:{" "}
              <a
                href="https://www.tiktok.com/@uni_mannheim"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                tiktok.com/@uni_mannheim
              </a>
            </li>
            <li>
              <em>Linkedin</em>:{" "}
              <a
                href="https://de.linkedin.com/school/university-of-mannheim/"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                linkedin.com/school/university-of-mannheim
              </a>
            </li>
            <li>
              <em>Facebook</em>:{" "}
              <a
                href="https://www.facebook.com/UniMannheim"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                facebook.com/UniMannheim
              </a>
            </li>
            <li>
              <em>Mastodon</em>:{" "}
              <a
                href="https://bawü.social/@unimannheim"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                bawü.social/@unimannheim
              </a>
            </li>
            <li>
              <em>YouTube</em>:{" "}
              <a
                href="https://www.youtube.com/@unimannheim"
                className="text-blue-500 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                youtube.com/@unimannheim
              </a>
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
};

export default Imprint;
